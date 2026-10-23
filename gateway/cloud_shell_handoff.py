"""Generate a user-assisted Cloud Shell diagnostic handoff.

Google's Cloud Shell REST API starts/configures/connects interactive sessions; it
does not expose a general arbitrary-command execution method. This module does
not call Google APIs or execute commands.
"""
from __future__ import annotations

import re
from typing import Any, Mapping


class HandoffError(ValueError):
    pass


DIAGNOSTIC_COMMANDS = {
    "identity": ("gcloud auth list --filter=status:ACTIVE --format='value(account)'",),
    "project": ("gcloud config get-value project",),
    "tool_versions": ("gcloud version",),
}


def build_cloud_shell_handoff(diagnostic: str, expected_project_id: str, task_id: str) -> dict[str, Any]:
    if diagnostic not in DIAGNOSTIC_COMMANDS:
        raise HandoffError("diagnostic is not allowlisted")
    if not isinstance(expected_project_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", expected_project_id):
        raise HandoffError("expected_project_id is malformed")
    if not isinstance(task_id, str) or not task_id.strip():
        raise HandoffError("task_id is required")
    commands = list(DIAGNOSTIC_COMMANDS[diagnostic])
    if diagnostic == "project":
        commands = [f"gcloud config get-value project"]
    return {
        "mode": "USER_ASSISTED_ONLY",
        "task_id": task_id,
        "diagnostic": diagnostic,
        "expected_project_id": expected_project_id,
        "commands": commands,
        "instructions": [
            "Open the intended Google Cloud Shell session yourself.",
            "Confirm the signed-in account and intended project before running anything.",
            "Run only the listed read-only diagnostic command(s); do not paste credentials or tokens.",
            "Return the raw output, timestamp, and the account/project context needed for review.",
            "Review and redact sensitive identifiers before sharing the output.",
        ],
        "verification": "The gateway has not executed this command. Treat returned output as user-supplied evidence until independently checked.",
    }


def verify_cloud_shell_receipt(diagnostic: str, expected_project_id: str, receipt: Mapping[str, Any]) -> dict[str, Any]:
    if diagnostic not in DIAGNOSTIC_COMMANDS:
        raise HandoffError("diagnostic is not allowlisted")
    if not isinstance(receipt, Mapping):
        raise HandoffError("receipt must be an object")
    raw_output = receipt.get("output")
    if not isinstance(raw_output, str) or not raw_output.strip():
        raise HandoffError("receipt output is required")
    if not isinstance(receipt.get("executed_at"), str) or not receipt["executed_at"].strip():
        raise HandoffError("receipt execution timestamp is required")
    if diagnostic == "project":
        observed = raw_output.strip().splitlines()[-1].strip()
        if observed != expected_project_id:
            raise HandoffError("Cloud Shell project output does not match the approved target")
        return {"status": "USER_REPORTED_MATCH", "observed_project_id": observed, "independently_verified": False}
    if diagnostic == "identity":
        accounts = [line.strip() for line in raw_output.splitlines() if line.strip()]
        if not accounts:
            raise HandoffError("no active account was reported")
        return {"status": "USER_REPORTED_OUTPUT_CAPTURED", "active_accounts": accounts, "independently_verified": False}
    return {"status": "USER_REPORTED_OUTPUT_CAPTURED", "independently_verified": False}
