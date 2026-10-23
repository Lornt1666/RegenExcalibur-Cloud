"""Minimal, non-dispatching policy evaluator for governed gateway task envelopes.

This module validates intent and authorization only. It never executes commands,
calls providers, sends applications, or treats client-supplied approval claims as
authoritative. Protected actions require a server-side approval_lookup result.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Callable, Mapping

CONTRACT_VERSION = "1JGM-GATEWAY-TASK-1.0"
OPERATIONS = {"repo.read_file", "repo.list_tree", "aigc.run_phase", "job.search", "job.prepare_application", "job.submit_application", "google.cloud_shell.read_only_diagnostic", "google.antigravity.prepare_handoff"}
PROTECTED = {"job.submit_application"}
PHASES = {f"phase{i}" for i in range(2, 24)}
DIAGNOSTICS = {"identity", "project", "tool_versions"}
SOURCES = {"remoteok", "remotive", "weworkremotely", "employer_careers"}
TOP_LEVEL = {"contract_version", "task_id", "idempotency_key", "initiated_by", "session_ref", "aigc_contract_ref", "target", "operation", "arguments", "resource_scope", "risk_level", "approval_id", "expires_at", "execution", "expected_outputs", "acceptance_criteria", "state", "audit_correlation_id"}
TARGET_KEYS = {"kind", "repository", "branch", "project_id", "environment", "workspace_id"}
EXECUTION_KEYS = {"timeout_seconds", "max_output_bytes"}
IDENTITY_KEYS = {"subject", "repositories", "projects", "can_approve"}
ApprovalLookup = Callable[[str], Mapping[str, Any] | None]


class ContractError(ValueError):
    """A task envelope is malformed or violates a policy invariant."""


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ContractError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def contract_digest(contract: Mapping[str, Any]) -> str:
    """Digest immutable task intent; approval metadata is deliberately excluded."""
    material = {k: v for k, v in contract.items() if k not in {"approval_id", "state"}}
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def validate_contract(contract: Mapping[str, Any], now: datetime | None = None) -> None:
    if not isinstance(contract, Mapping):
        raise ContractError("contract must be an object")
    extra, missing = set(contract) - TOP_LEVEL, TOP_LEVEL - set(contract)
    if extra:
        raise ContractError(f"unsupported contract fields: {sorted(extra)}")
    if missing:
        raise ContractError(f"missing contract fields: {sorted(missing)}")
    if contract["contract_version"] != CONTRACT_VERSION:
        raise ContractError("unsupported contract_version")
    for field in ("task_id", "idempotency_key", "initiated_by", "session_ref", "aigc_contract_ref", "audit_correlation_id"):
        if not isinstance(contract[field], str) or not contract[field].strip():
            raise ContractError(f"{field} must be a non-empty string")
    if not isinstance(contract["operation"], str) or contract["operation"] not in OPERATIONS:
        raise ContractError("operation is not allowlisted")
    if not isinstance(contract["risk_level"], str) or contract["risk_level"] not in {"low", "medium", "high", "critical"}:
        raise ContractError("invalid risk_level")
    if not isinstance(contract["state"], str) or contract["state"] not in {"REQUESTED", "AUTHORIZED", "REJECTED", "BLOCKED", "CANCELLED"}:
        raise ContractError("invalid gateway state")
    if not isinstance(contract["resource_scope"], list) or not contract["resource_scope"] or any(not isinstance(x, str) or not x.strip() for x in contract["resource_scope"]):
        raise ContractError("resource_scope must be a non-empty list of strings")
    if not isinstance(contract["expected_outputs"], list) or not isinstance(contract["acceptance_criteria"], list):
        raise ContractError("expected_outputs and acceptance_criteria must be arrays")
    execution = contract["execution"]
    if not isinstance(execution, Mapping) or set(execution) != EXECUTION_KEYS:
        raise ContractError("execution must contain only timeout_seconds and max_output_bytes")
    if type(execution["timeout_seconds"]) is not int or not 1 <= execution["timeout_seconds"] <= 900:
        raise ContractError("timeout_seconds must be between 1 and 900")
    if type(execution["max_output_bytes"]) is not int or not 1 <= execution["max_output_bytes"] <= 2_000_000:
        raise ContractError("max_output_bytes must be between 1 and 2000000")
    target = contract["target"]
    if not isinstance(target, Mapping) or set(target) - TARGET_KEYS or "kind" not in target:
        raise ContractError("target is malformed or contains unsupported fields")
    if not isinstance(target["kind"], str) or target["kind"] not in {"repository", "project", "cloud_shell", "antigravity", "job_platform"}:
        raise ContractError("target kind is not allowlisted")
    args, op = contract["arguments"], contract["operation"]
    if not isinstance(args, Mapping):
        raise ContractError("arguments must be an object")
    allowed_args = {
        "repo.read_file": {"path"}, "repo.list_tree": {"path"},
        "aigc.run_phase": {"phase", "mode"},
        "job.search": {"query", "sources", "location", "remote_preference"},
        "job.prepare_application": {"job_url", "profile_reference"},
        "job.submit_application": {"job_url", "application_reference"},
        "google.cloud_shell.read_only_diagnostic": {"diagnostic"},
        "google.antigravity.prepare_handoff": {"task_brief", "workspace_id"},
    }
    if set(args) - allowed_args[op]:
        raise ContractError("arguments contain unsupported keys for this operation")
    if op in {"repo.read_file", "repo.list_tree"}:
        path = args.get("path", ".")
        if not isinstance(path, str) or path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", path):
            raise ContractError("repository path must be relative")
        if any(part == ".." for part in path.replace("\\", "/").split("/")):
            raise ContractError("repository path traversal is prohibited")
        if not isinstance(target.get("repository"), str) or not target["repository"] or not isinstance(target.get("branch"), str) or not target["branch"]:
            raise ContractError("repository operations require repository and branch binding")
    if op == "aigc.run_phase" and (
        not isinstance(args.get("phase"), str) or args.get("phase") not in PHASES
        or not isinstance(args.get("mode"), str)
        or args.get("mode") not in {"dry_run", "real_data_read_only", "manual_handoff"}
    ):
        raise ContractError("AIGC phase or mode is not allowlisted")
    if op == "aigc.run_phase" and target["kind"] not in {"repository", "project"}:
        raise ContractError("AIGC phase execution requires an explicit repository or project target")
    if op == "job.search":
        if not isinstance(args.get("query"), str) or not args["query"].strip():
            raise ContractError("job search requires a non-empty query")
        if (not isinstance(args.get("sources"), list) or not args["sources"]
                or any(not isinstance(source, str) for source in args["sources"])
                or not set(args["sources"]) <= SOURCES):
            raise ContractError("job search sources are not allowlisted")
    if op == "job.prepare_application" and not all(isinstance(args.get(k), str) and args[k].strip() for k in ("job_url", "profile_reference")):
        raise ContractError("application preparation requires job_url and profile_reference")
    if op == "job.submit_application":
        if not all(isinstance(args.get(k), str) and args[k].strip() for k in ("job_url", "application_reference")):
            raise ContractError("submission requires a verified job URL and application reference")
        if contract["risk_level"] not in {"high", "critical"}:
            raise ContractError("job submission must be classified high or critical")
        if not isinstance(contract["approval_id"], str) or not contract["approval_id"]:
            raise ContractError("job submission requires a server-side approval reference")
    if op == "google.cloud_shell.read_only_diagnostic":
        if args.get("diagnostic") not in DIAGNOSTICS or not isinstance(target.get("project_id"), str) or not target["project_id"]:
            raise ContractError("Cloud Shell operation must be a typed read-only diagnostic with explicit project")
    if op == "google.antigravity.prepare_handoff":
        if not isinstance(args.get("task_brief"), str) or not args["task_brief"].strip():
            raise ContractError("Antigravity handoff requires a task brief")
        if target["kind"] != "antigravity" or not isinstance(target.get("workspace_id"), str) or not target["workspace_id"]:
            raise ContractError("Antigravity handoff requires an explicit workspace binding")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if _parse_time(contract["expires_at"], "expires_at") <= current:
        raise ContractError("task contract has expired")


def authorize_task(contract: Mapping[str, Any], identity: Mapping[str, Any], approval_lookup: ApprovalLookup, now: datetime | None = None) -> str:
    """Return ALLOW or raise ContractError; never dispatch work.

    identity must be populated by trusted server authentication, not request JSON.
    approval_lookup must read a durable server-side approval record.
    """
    validate_contract(contract, now)
    if not isinstance(identity, Mapping) or set(identity) - IDENTITY_KEYS:
        raise ContractError("trusted identity context is malformed")
    if not isinstance(identity.get("subject"), str) or not identity["subject"].strip():
        raise ContractError("trusted identity subject is missing")
    for field in ("repositories", "projects"):
        values = identity.get(field, [])
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise ContractError(f"trusted identity {field} scope is malformed")
    if "can_approve" in identity and type(identity["can_approve"]) is not bool:
        raise ContractError("trusted identity can_approve flag is malformed")
    if contract["initiated_by"] != identity["subject"]:
        raise ContractError("initiating identity mismatch")
    target = contract["target"]
    if contract["operation"].startswith("repo.") and target.get("repository") not in identity.get("repositories", []):
        raise ContractError("repository is outside authenticated identity scope")
    if contract["operation"] == "google.cloud_shell.read_only_diagnostic" and target.get("project_id") not in identity.get("projects", []):
        raise ContractError("project is outside authenticated identity scope")
    if contract["operation"] == "aigc.run_phase":
        repository = target.get("repository")
        project = target.get("project_id")
        if repository and repository not in identity.get("repositories", []):
            raise ContractError("AIGC repository is outside authenticated identity scope")
        if project and project not in identity.get("projects", []):
            raise ContractError("AIGC project is outside authenticated identity scope")
    if contract["operation"] in PROTECTED:
        if not identity.get("can_approve", False):
            raise ContractError("identity is not authorized to approve protected actions")
        record = approval_lookup(contract["approval_id"])
        if not isinstance(record, Mapping) or record.get("decision") != "APPROVED":
            raise ContractError("approval record missing or not approved")
        if record.get("task_id") != contract["task_id"]:
            raise ContractError("approval task binding mismatch")
        if record.get("contract_sha256") != contract_digest(contract):
            raise ContractError("approval contract digest mismatch")
        if record.get("approver") == contract["initiated_by"]:
            raise ContractError("self-approval is prohibited")
        if _parse_time(record.get("expires_at"), "approval.expires_at") <= (now or datetime.now(timezone.utc)).astimezone(timezone.utc):
            raise ContractError("approval has expired")
    return "ALLOW"
