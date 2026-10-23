# AIGC integration contract and approval boundary

Assessment basis: read-only GitHub source inspection on 2026-10-23. AIGC repository `Lornt1666/AIGC`, observed `main` SHA `5ff907ebd9a4d477100e38032db2b916b1aba9ab`. Recheck this SHA before implementation or release.

## Authoritative AIGC sources

- `config/aigc_omega_worker_v0_18_task_contract.json` declares the v0.18 execution-envelope intent and authority boundaries.
- `schemas/aigc_omega_worker_v0_1/task_contract_runtime_v0_18.schema.json` is the concrete runtime JSON Schema. It requires `contract_id`, `objective`, `authorized_scope`, `resource_budget`, `permitted_actions`, `evidence_requirements`, `postconditions`, `termination_conditions`, `retry_max`, `rollback_enabled`, `rollback_compensating_action`, `escalation_policy`, `owner`, `policy_reference`, and `expiration`.
- `src/core/omega_worker_task_contract.py` is the runtime dataclass validator inspected. It requires positive budget, unique permitted actions, evidence/postconditions/termination conditions, non-negative retries, explicit `idempotent` scope when retries are enabled, and a compensating action when rollback is enabled.
- `config/phase5_human_approval_gate.json` defines Phase 5 as authorization-only, prohibits external action during approval, disallows blanket approval, and invalidates approval when the artifact changes.
- `config/phase6_controlled_execution.json` sets `live_execution_allowed=false`, defaults to `manual_handoff`, requires Phase 5 approval for external actions, and invalidates execution on artifact, recipient or platform changes.
- `docs/AIGC_ORCHESTRATION_SECURITY_BOUNDARY.md` states the current orchestration fabric is a local control plane, not a live connector layer, and prohibits live webhooks, credential values, external sends, deployment and publishing.

## Current gateway integration status

`gateway/aigc_contract_bridge.py` is a **defense-in-depth local shape/policy check only**. It does not fetch the contract from AIGC, call the authoritative AIGC validator, create a Phase 4 proposal, obtain a Phase 5 approval packet, or invoke Phase 6 execution. The field `aigc_contract_ref` in the gateway envelope is a reference string, not proof that the referenced contract exists or was validated.

The bridge now mirrors the v0.18 schema field names and enforces the upstream retry/idempotency invariant, a gateway-provided action allowlist, resource budget cap, expiry, and rollback compensation rule. Passing its tests does not establish live AIGC integration.

## Required integration sequence

1. Resolve `aigc_contract_ref` through an authenticated, read-only AIGC interface or a verified repository snapshot pinned to an immutable commit.
2. Validate the exact contract with AIGC's authoritative v0.18 validator; record source SHA, contract digest, validator version, and outcome.
3. Bind contract owner, permitted actions, scope, resource budget, evidence requirements, expiry and termination conditions to the gateway task and trusted initiating identity.
4. Prepare a specific proposal through the existing Phase 2–4 workflow where applicable.
5. Require a distinct human approver for every Phase 5 protected action. Approval must bind to the exact action, artifact digest, destination/platform and expiry; any material change invalidates it.
6. Keep Phase 6 in its configured safe mode. The current AIGC config explicitly sets live execution false; do not enable live execution through the gateway.
7. Persist the Phase 6 receipt and audit evidence, independently verify the returned result, and only then present it for user acceptance.

## Acceptance tests before enabling any dispatch

- AIGC contract ID, owner or digest mismatch is rejected.
- Unknown or forbidden action is rejected before dispatch.
- Non-idempotent scope with retry enabled is rejected.
- Expired contract or approval is rejected.
- Changed artifact, recipient or platform invalidates approval.
- Phase 5 cannot dispatch; Phase 6 refuses an absent, expired, self-approved or mismatched approval.
- Current AIGC `live_execution_allowed=false` is respected by gateway policy.
- Every denial is durably recorded; no result is marked verified from an HTTP success response alone.

## Status

**PARTIAL / NOT LIVE-INTEGRATED.** Existing AIGC governance files were inspected and the gateway bridge has isolated tests. No AIGC runtime call, Phase 5 approval flow, Phase 6 execution, or external dispatch was performed.
