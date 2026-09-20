-- Dedicated login for the RomaLume API (2026-09-20).
--
-- The API connects through the Supabase pooler as romalume_app rather than
-- the postgres superuser. It owns nothing in public; it can read and write
-- the romalume schema, read public.clients, manage public.admin_users rows,
-- read auth.users, and (for the Postgres test suites) insert and delete
-- throwaway auth.users rows. Row level security still applies, so explicit
-- policies grant the role full access to romalume tables.
--
-- The password is not in this file. It lives in Railway (DATABASE_URL) and in
-- /mnt/d/dev/.env as ROMALUME_DATABASE_URL. Rotate with:
--   alter role romalume_app password '<new>';

-- create role romalume_app login password '<set out of band>';

grant usage on schema romalume to romalume_app;
grant all on all tables in schema romalume to romalume_app;
grant usage, select on all sequences in schema romalume to romalume_app;
grant execute on all functions in schema romalume to romalume_app;
alter default privileges in schema romalume grant all on tables to romalume_app;
alter default privileges in schema romalume grant usage, select on sequences to romalume_app;

grant usage on schema public to romalume_app;
grant select on public.clients to romalume_app;
grant select, insert, update, delete on public.admin_users to romalume_app;
grant execute on function public.can_access_client(uuid) to romalume_app;

grant usage on schema auth to romalume_app;
grant select, insert, delete on auth.users to romalume_app;

do $$
declare t text;
begin
  for t in select tablename from pg_tables where schemaname = 'romalume' loop
    execute format('drop policy if exists romalume_app_all on romalume.%I', t);
    execute format('create policy romalume_app_all on romalume.%I for all to romalume_app using (true) with check (true)', t);
  end loop;
end $$;

drop policy if exists romalume_app_admin_users on public.admin_users;
create policy romalume_app_admin_users on public.admin_users
  for all to romalume_app using (true) with check (true);
drop policy if exists romalume_app_clients on public.clients;
create policy romalume_app_clients on public.clients
  for select to romalume_app using (true);
