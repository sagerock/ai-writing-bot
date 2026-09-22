-- Marketing is a first-class content audience (Sage, 2026-09-22).
-- Admin preview and Qdrant retrieval use this same value; it is not a UI alias.

alter table romalume.library_documents
  drop constraint if exists library_documents_audience_check;
alter table romalume.library_documents
  add constraint library_documents_audience_check
  check (audience in ('staff','marketing','leadership','board','finance'));

alter table romalume.member_audiences
  drop constraint if exists member_audiences_audience_check;
alter table romalume.member_audiences
  add constraint member_audiences_audience_check
  check (audience in ('staff','marketing','leadership','board','finance'));

create or replace function romalume.user_audiences(target_client_id uuid)
returns text[]
language sql
security definer
set search_path = public, romalume
stable
as $$
  select case
    when exists (select 1 from public.admin_users a
                 join auth.users u on u.id = a.user_id
                 where a.user_id = auth.uid() and a.role = 'super_admin'
                   and lower(u.email::text) = 'sage@sagerock.com')
      then array['staff','marketing','leadership','board','finance']
    when public.can_access_client(target_client_id)
      then array(select distinct x from unnest(
             array['staff'] ||
             coalesce((select array_agg(m.audience) from romalume.member_audiences m
                       where m.client_id = target_client_id and m.user_id = auth.uid()),
                      array[]::text[])) as x)
    else array[]::text[]
  end;
$$;

grant execute on function romalume.user_audiences(uuid) to authenticated, service_role, romalume_app;
