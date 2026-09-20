-- RomaLume schema on the shared SageRock Supabase project.
-- Applied 2026-09-20. See docs/supabase-platform.md for the decisions.
--
-- Identity comes from public.clients / public.admin_users, which the email
-- tool owns. Every table here is scoped by client_id and guarded by the
-- existing public.can_access_client(uuid) function. Nothing in public changes.

create schema if not exists romalume;

-- Per-school settings. One row per client that uses RomaLume.
create table if not exists romalume.school_settings (
  client_id uuid primary key references public.clients(id) on delete cascade,
  comped boolean not null default false,
  comped_reason text,
  default_model text not null default 'auto',
  qdrant_collection text,            -- shared library collection Ask also reads
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Per-person settings and profile (replaces users/{uid}/settings/profile).
create table if not exists romalume.user_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  client_id uuid references public.clients(id) on delete set null,
  firebase_uid text unique,          -- filled by the one-time migration
  profile jsonb not null default '{}'::jsonb,
  default_model text not null default 'auto',
  credits integer not null default 100,
  credits_used integer not null default 0,
  subscription_status text not null default 'none',
  comped boolean not null default false,
  stripe_customer_id text,
  stripe_subscription_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Projects. owner_kind decides whether the whole school can see it.
create table if not exists romalume.projects (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  owner_kind text not null default 'user' check (owner_kind in ('user','client')),
  name text not null,
  kind text not null default 'memo',
  charge jsonb not null default '{}'::jsonb,
  context_mode text not null default 'full',
  default_model text,
  draft_markdown text not null default '',
  draft_version integer not null default 0,
  draft_saved_at timestamptz,
  next_source_num integer not null default 1,
  archived boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists projects_client_idx on romalume.projects(client_id, archived);
create index if not exists projects_user_idx on romalume.projects(user_id, archived);

create table if not exists romalume.sources (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references romalume.projects(id) on delete cascade,
  client_id uuid not null references public.clients(id) on delete cascade,
  source_num integer not null,
  label text not null,
  filename text not null,
  content_type text,
  size bigint,
  storage_path text,                 -- romalume-sources bucket
  status text not null default 'pending',
  pages integer,
  text_chars integer,
  chunk_count integer,
  estimated_tokens integer,
  indexed boolean not null default false,
  indexing_error text,
  uploaded_at timestamptz not null default now(),
  unique (project_id, source_num)
);
create index if not exists sources_project_idx on romalume.sources(project_id);

create table if not exists romalume.draft_versions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references romalume.projects(id) on delete cascade,
  client_id uuid not null references public.clients(id) on delete cascade,
  version integer not null,
  markdown text not null,
  reason text,
  saved_at timestamptz not null default now(),
  unique (project_id, version)
);

-- Chats inside a project, and standalone Quick Chat conversations.
create table if not exists romalume.conversations (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid references romalume.projects(id) on delete cascade,
  title text,
  model text,
  mode text,
  messages jsonb not null default '[]'::jsonb,
  message_count integer not null default 0,
  archived boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists conversations_user_idx on romalume.conversations(user_id, archived, updated_at desc);
create index if not exists conversations_project_idx on romalume.conversations(project_id);

-- Quick Chat uploaded documents (replaces users/{uid}/documents).
create table if not exists romalume.documents (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  filename text not null,
  content_type text,
  size bigint,
  storage_path text,
  chunk_count integer,
  indexed boolean not null default false,
  uploaded_at timestamptz not null default now()
);

-- School library registry: what is in the school's shared Qdrant collection.
-- Ask reads the collection; this table says where each chunk set came from.
create table if not exists romalume.library_documents (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  uploaded_by uuid references auth.users(id) on delete set null,
  source_id uuid references romalume.sources(id) on delete set null,
  title text not null,
  filename text not null,
  storage_path text,
  qdrant_collection text not null,
  chunk_count integer not null default 0,
  status text not null default 'indexed',
  created_at timestamptz not null default now()
);
create index if not exists library_client_idx on romalume.library_documents(client_id);

create table if not exists romalume.usage_logs (
  id bigint generated always as identity primary key,
  client_id uuid references public.clients(id) on delete set null,
  user_id uuid not null references auth.users(id) on delete cascade,
  model text not null,
  original_model text,
  input_tokens integer,
  output_tokens integer,
  estimated_cost_cents numeric(12,4),
  search_web boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists usage_logs_user_month_idx on romalume.usage_logs(user_id, created_at desc);

create table if not exists romalume.feedback (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  client_id uuid references public.clients(id) on delete set null,
  body text not null,
  context jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists romalume.stripe_webhook_events (
  event_id text primary key,
  received_at timestamptz not null default now()
);

-- updated_at maintenance
create or replace function romalume.touch_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

do $$
declare t text;
begin
  foreach t in array array['school_settings','user_settings','projects','conversations'] loop
    execute format('drop trigger if exists touch_updated_at on romalume.%I', t);
    execute format('create trigger touch_updated_at before update on romalume.%I
                    for each row execute function romalume.touch_updated_at()', t);
  end loop;
end $$;

-- Row level security. School-scoped rows: anyone who can access the client.
-- Personal rows (owner_kind = 'user'): the owner, or a super admin.
alter table romalume.school_settings   enable row level security;
alter table romalume.user_settings     enable row level security;
alter table romalume.projects          enable row level security;
alter table romalume.sources           enable row level security;
alter table romalume.draft_versions    enable row level security;
alter table romalume.conversations     enable row level security;
alter table romalume.documents         enable row level security;
alter table romalume.library_documents enable row level security;
alter table romalume.usage_logs        enable row level security;
alter table romalume.feedback          enable row level security;
alter table romalume.stripe_webhook_events enable row level security;

create policy school_settings_access on romalume.school_settings
  for all to authenticated using (public.can_access_client(client_id));

create policy user_settings_self on romalume.user_settings
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy projects_access on romalume.projects
  for all to authenticated
  using (user_id = auth.uid() or (owner_kind = 'client' and public.can_access_client(client_id)))
  with check (user_id = auth.uid() and public.can_access_client(client_id));

create policy sources_access on romalume.sources
  for all to authenticated
  using (exists (select 1 from romalume.projects p where p.id = project_id
                 and (p.user_id = auth.uid() or (p.owner_kind = 'client' and public.can_access_client(p.client_id)))));

create policy draft_versions_access on romalume.draft_versions
  for all to authenticated
  using (exists (select 1 from romalume.projects p where p.id = project_id
                 and (p.user_id = auth.uid() or (p.owner_kind = 'client' and public.can_access_client(p.client_id)))));

create policy conversations_self on romalume.conversations
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy documents_self on romalume.documents
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy library_access on romalume.library_documents
  for all to authenticated using (public.can_access_client(client_id)) with check (public.can_access_client(client_id));

create policy usage_logs_self on romalume.usage_logs
  for select to authenticated using (user_id = auth.uid());

create policy feedback_self on romalume.feedback
  for insert to authenticated with check (user_id = auth.uid());

-- stripe_webhook_events: service role only (no policies for authenticated).

grant usage on schema romalume to authenticated, service_role;
grant all on all tables in schema romalume to service_role;
grant select, insert, update, delete on all tables in schema romalume to authenticated;
grant usage, select on all sequences in schema romalume to authenticated, service_role;
alter default privileges in schema romalume grant all on tables to service_role;
alter default privileges in schema romalume grant select, insert, update, delete on tables to authenticated;

-- Center for Anthroposophy pilot, comped.
insert into romalume.school_settings (client_id, comped, comped_reason, qdrant_collection)
values ('22500cd6-052a-42ff-a0cb-4f3ba9125dfd', true, 'CfA pilot platform, per Sage 2026-09-20', 'cfa_library')
on conflict (client_id) do nothing;
