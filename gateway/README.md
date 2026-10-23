# Governed Gateway — initial contract and job-assessment primitives

## Status

This branch contains **non-dispatching policy primitives**. It is not a deployed gateway and does not yet provide an authenticated HTTP API, mobile UI, durable audit ledger, identity provider, provider execution, or application submission.

The contract is intended to bind a gateway request to an existing AIGC TaskContract through `aigc_contract_ref`. The existing AIGC contract and governance authority remain authoritative; this envelope does not replace them.

## Included

- `task_contract.schema.json`: versioned JSON Schema.
- `task_contract.py`: server-side envelope validation and policy checks.
- `test_task_contract.py`: authorization boundary regression tests.
- `job_agent.py`: deterministic listing normalization, deduplication, and evidence-bound skills/eligibility assessment.
- `cloud_shell_handoff.py`: typed read-only diagnostic handoff and receipt parser; no Cloud Shell API call or command execution.
- `antigravity_handoff.py`: workspace-bound user-assisted task handoff; no desktop, SDK, CLI, or managed-agent invocation.
- `aigc_contract_bridge.py`: defense-in-depth validation of the existing AIGC runtime v0.18 contract shape and a server-supplied operation allowlist; the authoritative AIGC validator remains upstream.
- `test_job_agent.py`: regression tests for URL hygiene, missing qualifications, unknown eligibility facts, and deduplication.
- `test_cloud_shell_handoff.py` and `test_antigravity_handoff.py`: regression tests for typed allowlists, explicit scope, and honest user-assisted status.
- `test_aigc_contract_bridge.py`: regression tests for contract reference binding, expiry, resource budget, and allowed actions.

## Critical integration requirements

1. Authenticate the caller in a trusted server component. Never populate `identity` from untrusted request JSON.
2. Bind repository and project allowlists to verified identity claims and server-side configuration.
3. Implement `approval_lookup` against a durable approval store. Bind approvals to task ID, immutable contract digest, approver identity, expiry, and the exact proposed external action.
4. Persist idempotency keys with a uniqueness constraint and atomic task creation; the pure validator alone does not prevent replay.
5. Persist durable audit events for both allowed and denied actions before any dispatch.
6. Keep policy evaluation separate from execution. The module intentionally does not execute commands or submit applications.
7. Verify job listings from actual source retrieval. The assessment function only assesses supplied records; it does not discover or verify live vacancies.
8. Keep job-profile data separate from infrastructure, repository-write, Cloud Shell, and Antigravity credentials.
9. Add provider adapters only after confirming supported authentication and execution interfaces. Cloud Shell and Antigravity operations are currently typed intent/handoff placeholders, not integrations.
10. Keep deployment, production IAM changes, external messages, and job applications behind explicit human approval.

## Initial acceptance matrix

| Requirement | Status | Evidence / limitation |
|---|---|---|
| Versioned gateway envelope | Implemented, CI pending for latest head | JSON Schema and Python validator in this branch |
| Operation argument allowlists | Implemented, CI pending | Unit tests cover invalid operations and path traversal |
| Trusted identity/target checks | Partial | Pure policy evaluator; identity provider and server configuration not integrated |
| Approval binding | Partial | Durable lookup is injected as a callback; production approval store absent |
| Replay protection | Not implemented | Requires persistent idempotency store and atomic create |
| Durable audit ledger | Not implemented | Must be integrated before any dispatch |
| Job listing normalization and deduplication | Implemented, CI pending | Pure functions and tests; no source connectors |
| Factual eligibility assessment | Implemented, CI pending | Only supplied verified profile facts are considered |
| Job application drafting | Not implemented | Requires approved profile-data source and document generation workflow |
| Job submission | Not implemented | No external submission connector; no submissions performed |
| Mobile gateway / ChatGPT connector | Not implemented | No authenticated API/UI in this branch |
| Cloud Shell handoff | Implemented, CI pending | Typed read-only command list and user-supplied receipt verifier; no Cloud Shell execution has been performed by this code |
| Antigravity handoff | Implemented, CI pending | Workspace-bound handoff package; no automated desktop/SDK/managed-agent call has been made |
| AIGC contract bridge | Partial, CI pending | Defense-in-depth shape/allowlist check; no live AIGC validator call or dispatch |
| Production deployment | Not authorized or performed | Draft PR only |

## External-service compatibility

See [the capability matrix and exact Neon resource blockers](EXTERNAL_SERVICE_MATRIX.md). No Neon resources have been inspected through an authenticated provider API, provisioned, or changed.

## Official integration research

- The [Cloud Shell REST reference](https://docs.cloud.google.com/shell/docs/reference/rest) documents environment start/get/authorize and SSH-key management, but no general arbitrary-command execution method. This branch therefore implements a user-assisted diagnostic handoff instead of claiming API command dispatch.
- The [Antigravity SDK](https://www.antigravity.google/docs/sdk/overview) is a supported Python runtime; the [managed Antigravity agent API](https://ai.google.dev/gemini-api/docs/antigravity-agent) supports remote sandbox interactions. Neither has been invoked from this repository. Select and configure one surface with explicit tool restrictions and credentials before implementing automated dispatch.

## Security notes

- A successful policy evaluation is not proof that an operation executed or succeeded.
- Client-side approval buttons are not an authorization boundary.
- A worker-reported digest is not independent content verification.
- The contract digest excludes `approval_id` and `state` so the approval reference/state transition do not alter the immutable task-intent digest; the approval store must still bind the approval record to the exact task and action.
- Never enable production dispatch until idempotency, durable audit, adapter identity binding, cancellation/recovery, and independent result verification are implemented and tested.
