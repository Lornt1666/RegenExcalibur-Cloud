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
