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
- The artifact unique key is owner/digest scoped, not job/revision scoped. The candidate must continue to compare the stored `job_id` and `revision_digest` before reusing an existing digest. The existing unique index prevents two concurrent inserts for the same owner/digest, but a race can still yield a unique-violation error to one caller; that caller must reconcile by re-reading and verifying the exact binding rather than treating the conflict as success.
- This was a catalog inspection only. No schema, data, permissions, function version, or production resource was modified.

This schema evidence removes the specific concern that `RETRYABLE_FAILURE` is invalid in the current live check constraint. It does not prove concurrency correctness or deployment readiness; those still require isolated database-level race tests and a non-production deployment test.
