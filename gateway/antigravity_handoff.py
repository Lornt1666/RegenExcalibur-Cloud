"""Prepare a reviewed task brief for manual execution in Antigravity.

This module does not invoke the desktop app, SDK, CLI, or managed Gemini API.
It produces a structured handoff with scope and verification requirements.
"""
from __future__ import annotations

from typing import Any, Mapping


class AntigravityHandoffError(ValueError):
    pass


def build_antigravity_handoff(task_contract: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(task_contract, Mapping):
        raise AntigravityHandoffError("task contract must be an object")
    if task_contract.get("operation") != "google.antigravity.prepare_handoff":
        raise AntigravityHandoffError("task is not an Antigravity handoff operation")
    target = task_contract.get("target")
    args = task_contract.get("arguments")
    if not isinstance(target, Mapping) or target.get("kind") != "antigravity":
        raise AntigravityHandoffError("target must be Antigravity")
    workspace_id = target.get("workspace_id")
    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise AntigravityHandoffError("workspace_id is required")
    if not isinstance(args, Mapping) or not isinstance(args.get("task_brief"), str) or not args["task_brief"].strip():
        raise AntigravityHandoffError("task_brief is required")
    return {
        "mode": "USER_ASSISTED_ONLY",
        "task_id": task_contract.get("task_id"),
        "workspace_id": workspace_id,
        "task_brief": args["task_brief"].strip(),
        "constraints": [
            "Confirm the exact workspace and repository before acting.",
            "Do not access credentials or unrelated workspaces.",
            "Do not deploy, change production permissions, send external communications, or submit applications.",
            "Request human approval before any protected action.",
            "Return a diff or artifact references, commands run, actual test results, and unresolved risks.",
            "The gateway has not run this task; returned output must be independently reviewed.",
        ],
        "evidence_required": ["workspace identifier", "changed-file list", "test output", "artifact references", "final status"],
    }
