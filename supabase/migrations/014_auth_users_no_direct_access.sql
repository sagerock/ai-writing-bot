-- romalume_app loses direct access to auth.users (2026-11-18).
--
-- Migration 007 granted select, insert, delete on auth.users. Nothing uses it:
--   - the API reads users only through romalume.auth_users() (user_store.list_users,
--     get_auth_user), a security-definer function owned by postgres (008);
--   - the Postgres test suites create and remove throwaway users only through
--     romalume.test_create_auth_user / test_delete_auth_user (008, tests/pg_fixture.py),
--     also security definer, limited to @romalume-tests.invalid on delete;
--   - foreign keys from romalume tables to auth.users need no grant on the
--     referenced table for the app role: Postgres runs the FK check as the owner
--     of auth.users, and ON DELETE CASCADE/SET NULL runs as the referencing
--     table's owner;
--   - romalume.user_audiences / can_read_audience read auth.users as definer.
-- So no direct statement on auth.users is needed by the app or the tests.
--
-- KEPT on purpose: `usage on schema auth`. The email tool's policy
-- "Users can read own admin record" on public.admin_users has no TO clause, so
-- it is evaluated for romalume_app too and calls auth.uid(); without schema
-- usage every RomaLume read of admin_users (user_store.list_users) would fail.
--
-- If 007's grant never took effect (008 notes the auth schema may refuse direct
-- grants), this revoke only raises a WARNING and changes nothing.
--
-- Verify after applying (read-only):
--   select has_table_privilege('romalume_app', 'auth.users', 'select'),
--          has_table_privilege('romalume_app', 'auth.users', 'insert'),
--          has_table_privilege('romalume_app', 'auth.users', 'delete');   -- all false
--
-- Rollback:
--   grant select, insert, delete on auth.users to romalume_app;

begin;

revoke all privileges on table auth.users from romalume_app;

commit;
