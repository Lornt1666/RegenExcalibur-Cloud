# Master Execution Mandate 004 — live acceptance matrix

**Snapshot date:** 2026-10-23  
**This is an evidence snapshot, not a production-readiness certification.** Update it whenever a branch head, environment, test, or external resource changes.

| ID | Requirement | Status | Repository/resource and exact evidence | Next action / blocker |
|---|---|---|---|---|
| WKR-01 | Worker lifecycle code type-check | PASS | PR #5 head `e30c482db78b0198b37ab6b121bd5e74d384562d`; [CI run 40021030545](https://github.com/Lornt1666/RegenExcalibur-Cloud/actions/runs/40021030545) | Keep PR draft; add database-level concurrency tests |
| WKR-02 | Worker isolated lifecycle regression suite | PASS | Same exact-head run: 10 passed, 0 failed | Test actual DB state transitions and stale-worker races in isolated staging |
| WKR-03 | Worker artifact durability and concurrency E2E | BLOCKED | Artifact-first pattern is implemented, but no transactional DB E2E or independent content hashing was run | Add safe staging fixture; retrieve and hash actual artifact content; prove cancellation/expiry races |
| WKR-04 | Worker deployment parity | BLOCKED | Live Supabase `autohouse-worker` is ACTIVE version 3, updated 2026-08-22; read-only source inspection confirms it only recovers expired `LEASED` jobs, lacks `RETRYABLE_FAILURE` recovery and artifact reconciliation, and terminally updates jobs without artifact-first persistence. Candidate PR #5 is not deployed. | Reconcile legacy leases, approve deployment, then verify deployed version and smoke tests | Reconcile legacy leases, approve deployment, then verify deployed version and smoke tests |
| GW-01 | Versioned gateway contract and policy evaluator | PASS | PR #6 tested head `b3366e44fbcfcef0146eedafb15ad3b10d26ebb6`; [CI run 40021345329](https://github.com/Lornt1666/RegenExcalibur-Cloud/actions/runs/40021345329); 35 tests passed | Review policy edge cases before integration |
| GW-02 | AIGC contract bridge | PASS | Same exact-head CI; validates runtime v0.18 shape, ref binding, expiry, budget, action allowlist | Connect to authoritative AIGC validator/runtime; current bridge is defense-in-depth only |
| GW-03 | Authenticated HTTP API, durable audit, idempotency, approval store | NOT_STARTED | No API server, trusted identity provider, durable approval database, or audit service is implemented in PR #6 | Implement the smallest server-side service using approved identity and persistence |
| MOB-01 | iPhone Safari mobile gateway | NOT_STARTED | No authenticated mobile interface or deployable API | Build after server auth/API and session lifecycle are ready |
| CHAT-01 | Direct ChatGPT conversation-to-gateway dispatch | BLOCKED | No connected gateway action/connector has been verified in this session | Add supported authenticated connector/action interface; until then use documented user-assisted handoff |
| CS-01 | Cloud Shell typed diagnostic handoff | PASS | PR #6 unit tests validate allowlisted read-only commands and receipt mismatch rejection | Run only in intended user account/project; verify actual identity/project and preserve evidence |
| CS-02 | Actual Cloud Shell command execution from gateway | BLOCKED | Official [Cloud Shell REST reference](https://docs.cloud.google.com/shell/docs/reference/rest) documents environment lifecycle, authorization, and SSH key management, but no general arbitrary-command REST method; no account credentials available here | Use an explicitly approved SSH/user-assisted route or provide a supported authenticated execution interface; prove target account/project and denial audit |
| AG-01 | Antigravity workspace-bound handoff | PASS | PR #6 unit tests validate workspace binding and user-assisted status | User must execute in the actual target workspace and return evidence |
| AG-02 | Automated Antigravity execution | BLOCKED | Official [SDK](https://www.antigravity.google/docs/sdk/overview) and [managed agent API](https://ai.google.dev/gemini-api/docs/antigravity-agent) are documented, but no credentials or actual agent execution are available in this session | Select one surface, constrain tools/hooks, configure approved credentials, and run a read-only staging test |
| JOB-01 | Job listing normalization, deduplication, eligibility assessment | PASS | PR #6 exact-head CI; test cases cover HTTPS URLs, retrieval timestamps, unknown qualifications, missing skills, and deduplication | Add real source connectors and retrieval timestamp/provenance |
| JOB-02 | Truthful application draft preparation | PASS | PR #6 exact-head CI; tests ensure only supplied profile facts are used and no submission occurs | Connect a verified user profile source with consent and retention controls |
| JOB-03 | Live vacancy discovery and application submission | NOT_STARTED | No public job source has been queried by the implementation; no applications submitted | Implement compliant source adapters and approval UI; test failed/duplicate submissions and confirmation capture |
| SUP-01 | Supabase advisor/catalog review | PASS | Read-only inspection on 2026-10-23; one anon GraphQL warning on `public.profiles`, 102 authenticated GraphQL exposure warnings | Continue per-object/function review; warnings do not by themselves prove all findings are exploitable |
| SUP-02 | Supabase profile/table permission remediation | BLOCKED | [Draft PR #7](https://github.com/Lornt1666/RegenExcalibur-Cloud/pull/7) contains a proposed SQL change; no production permissions or policies changed | Confirm profile-directory requirements and test proposal in a non-production branch; obtain explicit production authorization |
| EXT-01 | Neon target identity and capabilities | BLOCKED | Requested org `org-billowing-band-24504091`, project `delicate-feather-78716523`, branch label `production` not verified; no Neon API credential/connector available | Resolve immutable org/project/branch IDs using authenticated Neon API; follow `EXTERNAL_SERVICE_MATRIX.md` |
| SEC-01 | Negative authorization tests | PASS | PR #6 unit suite covers unknown fields, path traversal, scope mismatch, expired approvals, invalid actions, malformed scopes, and mismatched project/workspace | Add API-level tests proving denials happen before dispatch and are durably audited |
| REL-01 | Production release readiness | BLOCKED | PR #5 and PR #6 remain drafts; no deployment or release candidate certification | Complete API, staging E2E, Supabase remediation decision, service verification, review, rollback, and explicit release approval |

## Security review snapshot

Read-only Supabase inspection found:
- `public.profiles` has RLS enabled but `profiles_select_all USING (true)`, and the `anon` role has broad table privileges.
- `authenticated` has table-level INSERT/UPDATE on `profiles`; the current row policies bind rows by `auth.uid() = id` but do not restrict columns, creating a role-field privilege-escalation risk requiring prompt validation.
- `authenticated` has `MAINTAIN`, `TRUNCATE`, `TRIGGER`, and `REFERENCES` on `profiles`, `autohouse_jobs`, `autohouse_artifacts`, and `autohouse_events`.
- SECURITY DEFINER functions require individual review; intended public preflight functions must not be bulk-revoked without checking access gating and product requirements.

See [draft Supabase security review PR #7](https://github.com/Lornt1666/RegenExcalibur-Cloud/pull/7). No live changes were applied.

## Current repository baselines

- AIGC `main`: `5ff907ebd9a4d477100e38032db2b916b1aba9ab` (recheck before integration).
- Gateway repository base at time of PR #6: `RegenExcalibur-Webpage` / `c22e71ee06380097ddfde1dbabb3679102bb1f18`.
- Worker remediation PR #5 current candidate: `e30c482db78b0198b37ab6b121bd5e74d384562d`.
- Gateway contract PR #6 code-tested candidate: `b3366e44fbcfcef0146eedafb15ad3b10d26ebb6` (35 tests passed at exact-head CI); latest documentation-only candidate at this snapshot: `5e4f458da3e2b41e4df4e30827cba73130993852`.
- Supabase project reference: `wubfqagfkkylqzwswdfs`; live function `autohouse-worker` version 3 remains deployed; no production deployment or mutation performed.
