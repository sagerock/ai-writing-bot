-- RomaLume reads public.admin_users but never writes it (2026-11-18).
--
-- public.admin_users belongs to the email tool and decides who can reach which
-- client there; role = 'super_admin' opens every client of every app on this
-- project. Migration 007 gave romalume_app insert, update and delete on it plus
-- a FOR ALL policy, so a RomaLume bug or a stolen DATABASE_URL could grant
-- super admin. The app code no longer writes the table:
--   - the super-admin toggle (user_store.set_super_admin, POST /admin/users/{id}/role)
--     is gone; super admin is granted deliberately in the database by the owner;
--   - account deletion no longer deletes admin_users rows itself. They go with the
--     auth user: admin_users.user_id references auth.users(id) ON DELETE CASCADE
--     (email tool baseline, constraint admin_users_user_id_fkey).
--
-- RomaLume still reads the table (user_store.list_users, and the RLS helpers
-- romalume.user_audiences / can_read_audience, which run as their owner).
--
-- Rollback (restores the 007 behaviour; do not run without the owner's decision):
--   grant insert, update, delete on public.admin_users to romalume_app;
--   drop policy if exists romalume_app_admin_users_read on public.admin_users;
--   create policy romalume_app_admin_users on public.admin_users
--     for all to romalume_app using (true) with check (true);

begin;

revoke insert, update, delete, truncate, references, trigger
  on public.admin_users from romalume_app;
grant select on public.admin_users to romalume_app;

drop policy if exists romalume_app_admin_users on public.admin_users;
drop policy if exists romalume_app_admin_users_read on public.admin_users;
create policy romalume_app_admin_users_read on public.admin_users
  for select to romalume_app using (true);

commit;
