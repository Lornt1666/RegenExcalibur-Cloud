# Worker source-of-truth and deployment boundary — 2026-10-23

## Live service observed

- Supabase project: `wubfqagfkkylqzwswdfs`
- Function slug: `autohouse-worker`
- Status/version: `ACTIVE`, version `3`
- `verify_jwt=false`; the function performs custom GitHub OIDC verification in code.
- Live source fingerprint reported by Supabase: `a6f59d1e3733ca807492fcffb9ba496a0dc722f9ba04004cc47aa46be312fefe`
- Live source reports `VERSION = "v441"`.

## Repository reconciliation

The candidate PR adds `supabase/functions/autohouse-worker/index.ts`, `lifecycle.ts`, and tests, but those source files are **not present in the current PR base tree**. The existing `.github/workflows/autohouse-v440-worker-bridge.yml` invokes the live Supabase URL, checks out the repository, and executes `autohouse/v360/**`; it does not deploy the new `supabase/functions/autohouse-worker/**` source.

Therefore, passing CI on this PR proves isolated source checks only. It does **not** mean the live Supabase function has been remediated, and it does not mean the candidate source has been deployed.

## Material live/candidate differences

The live version retrieved from Supabase does not contain the candidate's `run_attempt` lease identity, expiry validation at start/finish, expired RUNNING reconciliation, artifact-before-success ordering, or strict job-type normalization. The live implementation recovers expired LEASED jobs only and writes the job's terminal state before inserting the artifact. It also permits finish from LEASED or RUNNING and its lease/start/finish checks do not bind the worker to the workflow attempt and current lease expiry.

## Safe next actions

1. Keep this PR draft; do not claim production remediation.
2. Review the complete candidate source against the live deployed source and schema.
3. Add an explicit, reviewed deployment procedure (or deployment workflow gated by protected-environment approval) that deploys the reviewed candidate to the correct function slug.
4. Validate deployment and rollback using a non-production Supabase project/branch first.
5. Obtain explicit production deployment authorization.
6. After authorized deployment, verify the function version/source fingerprint, run non-destructive OIDC self-test and access-negative tests, inspect logs, and reconcile any legacy leases written with only `run_id`.

No production deployment or live database mutation was performed as part of this review.

## Live database schema check (read-only, 2026-10-23)

The connected Supabase catalog was queried read-only after this candidate was reviewed:

- `public.autohouse_jobs_state_check` explicitly permits `QUEUED`, `LEASED`, `RUNNING`, `SUCCEEDED`, `RETRYABLE_FAILURE`, `FAILED`, and `CANCELLED`. The candidate's `RETRYABLE_FAILURE` recovery value is therefore compatible with the current live CHECK constraint.
- `public.autohouse_artifacts` has unique index `autohouse_artifacts_owner_id_artifact_digest_key` on `(owner_id, artifact_digest)`.
- `public.autohouse_jobs` has unique index `autohouse_jobs_owner_id_idempotency_key_key` on `(owner_id, idempotency_key)`.
- The artifact unique key is owner/digest scoped, not job/revision scoped. The candidate compares the stored `job_id` and `revision_digest` before reusing an existing digest. If insert returns an error, the current candidate re-reads the owner/digest row and proceeds only when owner, job, revision and artifact digest all match exactly. This covers the common concurrent-unique-conflict path at source level; database-level race behavior still requires staging integration tests.
- This was a catalog inspection only. No schema, data, permissions, function version, or production resource was modified.

This schema evidence removes the specific concern that `RETRYABLE_FAILURE` is invalid in the current live check constraint. It does not prove concurrency correctness or deployment readiness; those still require isolated database-level race tests and a non-production deployment test.

## Latest artifact-conflict remediation and exact-head CI (2026-10-23)

- Candidate head: `bb70cd610e8d35540de4950819d64aeac80b23f2`.
- [Exact-head CI run 40024252106](https://github.com/Lornt1666/RegenExcalibur-Cloud/actions/runs/40024252106) checked out this SHA; Deno type-check passed and all 10 isolated lifecycle tests passed.
- The latest source catches an artifact insert error, re-reads by `owner_id + artifact_digest`, and accepts the result only when `owner_id`, `job_id`, `revision_digest`, and `artifact_digest` match the expected binding. If the lookup fails, no exact row exists, or any binding differs, completion fails closed and the job remains nonterminal.
- This is still source-level logic plus isolated lifecycle tests. It does not prove the concurrent insert race against a real PostgreSQL instance, independent hashing of artifact content, or deployment behavior.
