-- Audience tiers inside a school, and a school voice.
-- From docs/cfa-pilot-brief.md §1a and §1c (Sage, 2026-09-20).
--
-- A school's library has tiers: staff, leadership, board, finance. A document
-- carries one audience tag; a person holds a set of audiences for the school.
-- Visibility is enforced here in Postgres. The Qdrant side must carry the same
-- tag in point metadata and pre-filter on it at query time (application work,
-- phase 4); this migration is the source of truth the filter reads from.

-- One tag per library document. Named by audience, never by level.
alter table romalume.library_documents
  add column if not exists audience text not null default 'staff'
    check (audience in ('staff','leadership','board','finance'));
create index if not exists library_audience_idx
  on romalume.library_documents(client_id, audience);

-- Which audiences a person holds at a school. Lives in romalume, not on
-- public.admin_users, which belongs to the email tool.
create table if not exists romalume.member_audiences (
  client_id uuid not null references public.clients(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  audience text not null check (audience in ('staff','leadership','board','finance')),
  granted_by uuid references auth.users(id) on delete set null,
  granted_at timestamptz not null default now(),
  primary key (client_id, user_id, audience)
);
alter table romalume.member_audiences enable row level security;

-- Super admins hold every audience everywhere. Everyone else holds what they
-- were granted, plus 'staff' whenever they can access the school at all.
create or replace function romalume.user_audiences(target_client_id uuid)
returns text[]
language sql
security definer
set search_path = public, romalume
stable
as $$
  select case
    when exists (select 1 from public.admin_users a
                 where a.user_id = auth.uid() and a.role = 'super_admin')
      then array['staff','leadership','board','finance']
    when public.can_access_client(target_client_id)
      then array(select distinct x from unnest(
             array['staff'] ||
             coalesce((select array_agg(m.audience) from romalume.member_audiences m
                       where m.client_id = target_client_id and m.user_id = auth.uid()),
                      array[]::text[])) as x)
    else array[]::text[]
  end;
$$;
grant execute on function romalume.user_audiences(uuid) to authenticated, service_role;

create or replace function romalume.can_read_audience(target_client_id uuid, target_audience text)
returns boolean
language sql
security definer
set search_path = public, romalume
stable
as $$
  select target_audience = any (romalume.user_audiences(target_client_id));
$$;
grant execute on function romalume.can_read_audience(uuid, text) to authenticated, service_role;

-- Library documents: readable only within the caller's audiences. Writing a
-- document at an audience you do not hold is also refused.
drop policy if exists library_access on romalume.library_documents;
create policy library_read on romalume.library_documents
  for select to authenticated
  using (romalume.can_read_audience(client_id, audience));
create policy library_write on romalume.library_documents
  for insert to authenticated
  with check (romalume.can_read_audience(client_id, audience));
create policy library_update on romalume.library_documents
  for update to authenticated
  using (romalume.can_read_audience(client_id, audience))
  with check (romalume.can_read_audience(client_id, audience));
create policy library_delete on romalume.library_documents
  for delete to authenticated
  using (romalume.can_read_audience(client_id, audience));

-- Members can see who holds what at their school; only leadership grants.
create policy member_audiences_read on romalume.member_audiences
  for select to authenticated
  using (public.can_access_client(client_id));
create policy member_audiences_grant on romalume.member_audiences
  for all to authenticated
  using (romalume.can_read_audience(client_id, 'leadership'))
  with check (romalume.can_read_audience(client_id, 'leadership'));

-- School voice: derived notes so a letter sounds like the school whoever asked.
alter table romalume.school_settings
  add column if not exists voice_notes text,
  add column if not exists voice_updated_at timestamptz,
  add column if not exists voice_updated_by uuid references auth.users(id) on delete set null;
comment on column romalume.school_settings.voice_notes is
  'Curated house voice for drafts, editable by leadership. Derived from published content (see docs/cfa-pilot-brief.md §1c).';
