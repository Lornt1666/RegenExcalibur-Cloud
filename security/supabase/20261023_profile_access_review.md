# Supabase security review — 2026-10-23

**Status: READ-ONLY REVIEW COMPLETE FOR THE QUERIED OBJECTS; REMEDIATION NOT APPLIED.**

Project reference: `wubfqagfkkylqzwswdfs`  
Review mode: live read-only SQL/catalog inspection and Supabase security advisor.  
Authorization boundary: no production grants, policies, functions, schema, or data were changed.

## Confirmed findings

### SEC-PROFILE-001 — Public profile disclosure (high priority)

Live security advisor reported `pg_graphql_anon_table_exposed` for `public.profiles`. The live catalog shows:
- RLS is enabled, but policy `profiles_select_all` applies to `{public}` with `USING (true)`.
- `anon` has table-level SELECT and other privileges on `public.profiles`.
- The table contains `email`, `full_name`, `avatar_url`, `role`, `bio`, `website`, and `location`, plus timestamps.
- The current SELECT policy is not row-restrictive. RLS being enabled does not make this table private when a permissive policy returns true.

**Risk:** anonymous callers may be able to enumerate profile rows and fields exposed through the API. This review did not retrieve profile data or attempt an unauthorized API read.

### SEC-PROFILE-002 — User-controlled privilege field risk (high priority)

The live catalog shows table-level INSERT and UPDATE grants to `authenticated`, while `profiles_insert_own` checks only `auth.uid() = id` and `profiles_update_own` checks only `auth.uid() = id`. The table has a `role` column defaulting to `member`.

Those row policies do not restrict which columns an authenticated user may set. With table-level INSERT/UPDATE grants, a user may be able to set or update their own `role` value, subject to the actual API path and database privileges. This is a **confirmed privilege-design flaw requiring urgent validation and remediation**, not a claim that exploitation was performed.

### SEC-GRANT-003 — Excess table privileges

Live catalog grants for `authenticated` include `MAINTAIN`, `TRUNCATE`, `TRIGGER`, and `REFERENCES` on `public.profiles`, `public.autohouse_jobs`, `public.autohouse_artifacts`, and `public.autohouse_events`. Row-level security does not filter TRUNCATE. These privileges are not normally needed for application-level row CRUD and should be removed unless a documented requirement proves otherwise.

### SEC-FUNCTION-004 — SECURITY DEFINER execution inventory required

The live catalog lists multiple SECURITY DEFINER functions executable by `authenticated`. It also lists these as executable by `anon`:
- `autohouse_anonymous_preflight(uuid, integer)`
- `autohouse_construction_release_preflight(uuid, integer)`
- `autohouse_project_source_currency_preflight(uuid, integer)`
- `autohouse_regulatory_source_freshness()`
- `handle_new_user()`

The three project-specific preflight functions call access-context logic and return a denial when public preflight is not enabled; their intended public use must be preserved if that is a product requirement. The global regulatory freshness function returns source-currency summaries. `handle_new_user()` is a trigger function, not a normal application RPC. It should not be directly executable by application roles. All SECURITY DEFINER functions still require a per-function audit of argument validation, owner checks, search path, side effects, and intended callers; do not bulk-revoke the whole function set.

## Recommended remediation proposal

The adjacent SQL file is a **review proposal only**, not a production migration and not executed. It:
- Removes anonymous table access to `profiles`.
- Replaces the permissive SELECT policy with owner-only authenticated SELECT.
- Removes table-level INSERT/UPDATE and grants only the profile fields that users should edit, excluding `role`, `email`, and `id` from user-controlled updates.
- Removes unnecessary MAINTAIN/TRUNCATE/TRIGGER/REFERENCES privileges from the four reviewed tables.
- Removes direct EXECUTE grants on the trigger function `handle_new_user()`.

Before applying, inspect client code for legitimate profile-directory behavior and profile writes. If a public directory is needed, expose a **separate sanitized view** containing only approved public fields, with explicit grants and row/column behavior. Do not restore public access to the base table.

## Required pre-deployment checks

1. Inventory all callers of `profiles` and `handle_new_user()`, including signup trigger behavior.
2. Confirm whether public profile discovery is an intended feature; if so, define a sanitized view contract.
3. Run negative tests as anon: cannot enumerate profiles, read emails, insert/update/delete profiles, or invoke the trigger function.
4. Run authenticated tests: can read own profile, cannot read another user's profile, cannot set `role`, `email`, or `id`, can edit only approved profile fields, and cannot TRUNCATE reviewed tables.
5. Run signup tests to ensure the auth trigger still creates profiles after EXECUTE revocation.
6. Verify owner/service-role workflows and worker job/artifact CRUD still function.
7. Re-run the Supabase security advisor and catalog grant queries.
8. Apply only through the approved migration/change process with explicit production authorization.

## Evidence captured

- Security advisor refreshed read-only at `2026-10-23T20:59:21Z`: one anon GraphQL exposure finding for `public.profiles`; 102 authenticated GraphQL exposure findings; five `SECURITY DEFINER` functions executable by `anon`; 93 `SECURITY DEFINER` functions executable by `authenticated`. Examples were inspected, but the complete 98-function inventory still requires per-function review before any blanket privilege changes. The advisor counts are warnings about discoverability/execution grants, not proof that each object is exploitable.
- RLS state: enabled for `profiles`, `autohouse_jobs`, `autohouse_artifacts`, and `autohouse_events`.
- Policies: `profiles_select_all USING (true)`; owner-scoped policies on jobs, artifacts and events using `owner_id = auth.uid()`; owner-scoped insert/update/delete policies on profiles.
- Grants: anon has broad table privileges on profiles; authenticated has broad table privileges on the four reviewed tables, including TRUNCATE.
- Read-only SQL only. No user rows were read, no exploit attempts were made, and no live changes were applied.

## Disposition

**BLOCKED pending explicit production-change authorization and application compatibility review.** The recommended next step is to review the proposal, add integration tests in a safe branch/staging project, and then request approval for a controlled production migration.

## Follow-up read-only refresh (2026-10-23 21:04 UTC)

The Supabase security advisor was queried again. It still reports:
- 1 anonymous GraphQL table exposure: `public.profiles`.
- 102 authenticated-role GraphQL table exposure findings.
- 5 `SECURITY DEFINER` functions executable by `anon`.
- 93 `SECURITY DEFINER` functions executable by `authenticated`.

A separate read-only `information_schema.role_table_grants` query confirmed that `anon` currently has DELETE, INSERT, REFERENCES, SELECT, TRIGGER, TRUNCATE and UPDATE grants on `public.profiles`. `authenticated` has DELETE, INSERT, REFERENCES, SELECT, TRIGGER, TRUNCATE and UPDATE grants on `public.profiles`, `public.autohouse_jobs`, `public.autohouse_artifacts`, and `public.autohouse_events`. This reinforces that the proposal should be evaluated against all actual grants, not merely the advisor's SELECT/GraphQL exposure warning.

The advisor observations are timestamped `2026-10-23T21:04:36.303Z`. These findings remain risk indicators, not proof that an exploit was performed. No row data was retrieved, no access attempt was made, and no live grant, policy, function, schema or data was modified.

**Disposition remains unchanged:** proposal only; validate the application and signup path in a non-production environment, audit all 98 SECURITY DEFINER function grants individually, and obtain explicit approval before any production change.
