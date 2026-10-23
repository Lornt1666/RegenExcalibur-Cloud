# Governed Gateway — initial contract and job-assessment primitives

## Status

This branch contains **non-dispatching policy primitives**. It is not a deployed gateway and does not yet provide an authenticated HTTP API, mobile UI, durable audit ledger, identity provider, provider execution, or application submission.

The contract is intended to bind a gateway request to an existing AIGC TaskContract through `aigc_contract_ref`. The existing AIGC contract and governance authority remain authoritative; this envelope does not replace them.

## Included

- `task_contract.schema.json`: versioned JSON Schema.
- `task_contract.py`: server-side envelope validation and policy checks.
- `test_task_contract.py`: authorization boundary regression tests.
- `job_agent.py`: deterministic listing normalization, deduplication, and evidence-bound skills/eligibility assessment.
- `test_job_agent.py`: regression tests for URL hygiene, missing qualifications, unknown eligibility facts, and deduplication.

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
| Cloud Shell adapter | Not implemented | No Cloud Shell execution has been performed by this code |
| Antigravity adapter | Not implemented | Only typed handoff validation; no automated UI control |
| AIGC integration | Not implemented | Contract reference exists; runtime validator/dispatcher integration remains |
| Production deployment | Not authorized or performed | Draft PR only |

## Security notes

- A successful policy evaluation is not proof that an operation executed or succeeded.
- Client-side approval buttons are not an authorization boundary.
- A worker-reported digest is not independent content verification.
- The contract digest excludes `approval_id` and `state` so the approval reference/state transition do not alter the immutable task-intent digest; the approval store must still bind the approval record to the exact task and action.
- Never enable production dispatch until idempotency, durable audit, adapter identity binding, cancellation/recovery, and independent result verification are implemented and tested.
