"""Application service for governed task intake; never dispatches execution."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from gateway.ledger import GatewayLedger
from gateway.task_contract import (
    ApprovalLookup, ContractError, authorize_task, contract_digest, validate_contract,
)


class IntakeDenied(PermissionError):
    """Task intake was rejected by validation or authorization."""


class GatewayIntakeService:
    def __init__(self, ledger: GatewayLedger):
        self.ledger = ledger

    def submit(
        self,
        contract: Mapping[str, Any],
        trusted_identity: Mapping[str, Any] | None,
        approval_lookup: ApprovalLookup,
    ) -> dict[str, Any]:
        """Validate, authorize and persist intake using server-authenticated identity.

        The trusted_identity argument must come from authentication middleware;
        this service never reads identity claims from the contract body.
        """
        subject = trusted_identity.get("subject") if isinstance(trusted_identity, Mapping) else None
        actor = subject.strip() if isinstance(subject, str) and subject.strip() else "unauthenticated"
        action_value = contract.get("operation") if isinstance(contract, Mapping) else None
        action = action_value if isinstance(action_value, str) and action_value.strip() else "TASK_CREATE"
        digest = None
        try:
            if isinstance(contract, Mapping):
                try:
                    digest = contract_digest(contract)
                except (TypeError, ValueError):
                    digest = None
            if not isinstance(trusted_identity, Mapping):
                raise ContractError("trusted authenticated identity is required")
            validate_contract(contract)
            if contract.get("state") != "REQUESTED":
                raise ContractError("client may submit only REQUESTED tasks; state is server-controlled")
            authorize_task(contract, trusted_identity, approval_lookup)
            normalized = dict(contract)
            normalized["state"] = "AUTHORIZED"
            return self.ledger.create_task(normalized, actor)
        except (ContractError, ValueError, TypeError) as exc:
            self.ledger.record_denial(
                actor=actor,
                action=action,
                reason_code="INTAKE_VALIDATION_OR_AUTHORIZATION_DENIED",
                task_id=contract.get("task_id") if isinstance(contract, Mapping) and isinstance(contract.get("task_id"), str) else None,
                digest=digest,
            )
            raise IntakeDenied(str(exc)) from exc
