# AIGC Integration Boundary

Assessment date: 2026-10-23.

## Authoritative upstream source inspected

- AIGC repository: [Lornt1666/AIGC](https://github.com/Lornt1666/AIGC)
- Inspected `main` SHA: `5ff907ebd9a4d477100e38032db2b916b1aba9ab`
- [Authoritative TaskContract dataclass](https://github.com/Lornt1666/AIGC/blob/5ff907ebd9a4d477100e38032db2b916b1aba9ab/src/core/omega_worker_task_contract.py)
- [Phase 5 human approval gate](https://github.com/Lornt1666/AIGC/blob/5ff907ebd9a4d477100e38032db2b916b1aba9ab/src/phase5_human_approval_gate.py)
- [Phase 6 controlled execution](https://github.com/Lornt1666/AIGC/blob/5ff907ebd9a4d477100e38032db2b916b1aba9ab/src/phase6_controlled_execution.py)

The TaskContract dataclass defines: `contract_id`, `objective`, `authorized_scope`, `resource_budget`, `permitted_actions`, `evidence_requirements`, `postconditions`, `termination_conditions`, `retry_max`, `rollback_enabled`, `rollback_compensating_action`, `escalation_policy`, `owner`, `policy_reference`, and `expiration`. Its constructor enforces required identity/scope, positive budget, non-empty action/evidence/postcondition/termination collections, unique actions, retry/idempotency consistency, and rollback compensating-action consistency.

## Gateway behavior currently implemented

`gateway/aigc_contract_bridge.py` performs defense-in-depth shape checks, expiration validation, budget bounds, retry/idempotency consistency, rollback checks, and a server-supplied gateway action allowlist. It returns `VALIDATED_SHAPE_AND_GATEWAY_ALLOWLIST` and explicitly marks `authoritative_aigc_validation: REQUIRED_UPSTREAM` and `execution_dispatched: false`.

This bridge is **not** a live call to AIGC's TaskContract validator. It does not retrieve an authoritative contract from AIGC, prove the referenced contract is the current approved object, invoke Phase 5, or dispatch through Phase 6. A unit test of the bridge proves only the gateway's local validation behavior.

## Required integration sequence

1. Resolve `aigc_contract_ref` to a specific authoritative AIGC contract using an approved, authenticated interface.
2. Verify contract identity, owner, target scope, expiration, action list, resource budget, evidence requirements, postconditions, retry policy, and immutable contract digest.
3. Invoke the existing AIGC validation path; do not duplicate or replace its authority with gateway claims.
4. For protected or consequential actions, require a durable Phase 5 approval packet bound to the exact contract digest, target, permitted action, expiry, and approver identity.
5. Dispatch only through the existing Phase 6 controlled-execution path or an explicitly approved adapter that preserves its policy and audit contract.
6. Capture executor identity, operation ID, timestamps, exit/result state, and artifacts.
7. Independently verify output and postconditions; persist evidence before marking the task complete.
8. Preserve correlation from gateway task ID → AIGC contract ID/digest → approval packet → execution receipt → evidence and final acceptance.
9. Test expiry, replay, target mismatch, changed contract after approval, denied approval, cancellation race, failed artifact persistence, stale executor response, and false success claims.

## Current status

- Local contract-shape/allowlist bridge and unit tests: implemented.
- AIGC repository source: inspected at the SHA above.
- Authenticated contract retrieval from AIGC: not implemented.
- Live invocation of authoritative AIGC validation: not verified.
- Phase 5 approval integration: not implemented end-to-end.
- Phase 6 execution dispatch: intentionally not implemented by this gateway candidate.
- End-to-end gateway-to-AIGC execution and evidence return: not verified.

No AIGC repository files, production resources, credentials, or live execution state were changed by this inspection.
