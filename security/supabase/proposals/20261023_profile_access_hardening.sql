-- REVIEW PROPOSAL ONLY — DO NOT APPLY TO PRODUCTION WITHOUT EXPLICIT APPROVAL.
-- Target project reference: wubfqagfkkylqzwswdfs
-- Based on read-only catalog inspection dated 2026-10-23.
-- Validate application compatibility and test in a non-production branch first.

BEGIN;

-- Stop anonymous access to profile data and replace the public SELECT policy.
REVOKE ALL PRIVILEGES ON TABLE public.profiles FROM anon;
DROP POLICY IF EXISTS profiles_select_all ON public.profiles;
DROP POLICY IF EXISTS profiles_select_own ON public.profiles;
CREATE POLICY profiles_select_own
  ON public.profiles
  FOR SELECT
  TO authenticated
  USING (auth.uid() = id);

-- Avoid table-level INSERT/UPDATE, which could let a user set their own role.
REVOKE INSERT, UPDATE ON TABLE public.profiles FROM authenticated;
GRANT INSERT (id, full_name, avatar_url, bio, website, location)
  ON TABLE public.profiles TO authenticated;
GRANT UPDATE (full_name, avatar_url, bio, website, location)
  ON TABLE public.profiles TO authenticated;

-- RLS remains responsible for row ownership. These capabilities are not needed
-- for ordinary app row CRUD and bypass row-level isolation or widen DDL powers.
REVOKE TRUNCATE, TRIGGER, REFERENCES
  ON TABLE public.profiles, public.autohouse_jobs,
             public.autohouse_artifacts, public.autohouse_events
  FROM authenticated;

-- This is a trigger function, not a public RPC. Signup-trigger behavior must
-- be verified after this privilege change in a non-production test project.
REVOKE EXECUTE ON FUNCTION public.handle_new_user()
  FROM PUBLIC, anon, authenticated;

COMMIT;

-- No rollback that restores profiles_select_all or anonymous base-table access
-- is provided. If the product requires a public directory, implement a separate
-- sanitized view and grant access only to that reviewed public representation.
