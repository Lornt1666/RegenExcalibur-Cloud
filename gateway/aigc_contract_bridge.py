"""Defense-in-depth adapter for AIGC TaskContract Runtime v0.18.

The authoritative AIGC validator remains upstream. This module validates the
contract shape and enforces a caller-supplied server-side action allowlist before
the gateway considers dispatch. It does not execute tasks or fetch AIGC data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


class AIGCContractError(ValueError):
    pass


REQUIRED_FIELDS = {
    "contract_id", "objective", "authorized_scope", "resource_budget",
    "permitted_actions", "evidence_requirements", "postconditions",
    "termination_conditions", "retry_max", "rollback_enabled",
    "rollback_compensating_action", "escalation_policy", "owner",
    "policy_reference", "expiration",
}


def validate_aigc_runtime_contract(
    contract: Mapping[str, Any],
    expected_contract_id: str,
    allowed_actions: set[str],
    max_resource_budget: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(contract, Mapping):
        raise AIGCContractError("AIGC contract must be an object")
    if set(contract) != REQUIRED_FIELDS:
        raise AIGCContractError("AIGC runtime contract fields do not match v0.18 schema")
    for field in ("contract_id", "objective", "authorized_scope", "escalation_policy", "owner", "policy_reference", "expiration"):
        if not isinstance(contract[field], str) or not contract[field].strip():
            raise AIGCContractError(f"{field} must be a non-empty string")
    if contract["contract_id"] != expected_contract_id:
        raise AIGCContractError("AIGC contract reference mismatch")
    if type(contract["resource_budget"]) is not int or not 1 <= contract["resource_budget"] <= max_resource_budget:
        raise AIGCContractError("AIGC resource budget exceeds server-side policy")
    if type(contract["retry_max"]) is not int or not 0 <= contract["retry_max"] <= 5:
        raise AIGCContractError("AIGC retry_max must be between 0 and 5")
    if contract["retry_max"] > 0 and "idempotent" not in contract["authorized_scope"].lower():
        raise AIGCContractError("retry authorization must explicitly declare idempotency")
    if type(contract["rollback_enabled"]) is not bool:
        raise AIGCContractError("rollback_enabled must be boolean")
    if not isinstance(contract["rollback_compensating_action"], str):
        raise AIGCContractError("rollback_compensating_action must be a string")
    if contract["rollback_enabled"] and not contract["rollback_compensating_action"].strip():
        raise AIGCContractError("rollback requires a compensating action")
    for field in ("permitted_actions", "evidence_requirements", "postconditions", "termination_conditions"):
        values = contract[field]
        if not isinstance(values, list) or not values or any(not isinstance(x, str) or not x.strip() for x in values):
            raise AIGCContractError(f"{field} must be a non-empty list of strings")
    actions = contract["permitted_actions"]
    if len(set(actions)) != len(actions):
        raise AIGCContractError("permitted_actions must be unique")
    if not set(actions) <= allowed_actions:
        raise AIGCContractError("AIGC contract requests actions outside the gateway allowlist")
    try:
        expiry = datetime.fromisoformat(contract["expiration"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise AIGCContractError("expiration must be ISO-8601") from exc
    if expiry.tzinfo is None:
        raise AIGCContractError("expiration must include a timezone")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if expiry.astimezone(timezone.utc) <= current:
        raise AIGCContractError("AIGC contract has expired")
    return {
        "contract_id": contract["contract_id"],
        "owner": contract["owner"],
        "authorized_scope": contract["authorized_scope"],
        "permitted_actions": list(actions),
        "resource_budget": contract["resource_budget"],
        "retry_max": contract["retry_max"],
        "expiration": expiry.astimezone(timezone.utc).isoformat(),
        "status": "VALIDATED_SHAPE_AND_GATEWAY_ALLOWLIST",
        "authoritative_aigc_validation": "REQUIRED_UPSTREAM",
        "execution_dispatched": False,
    }
