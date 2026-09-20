-- Columns the Postgres data layer needs to replace Firestore outright.
-- Sage decided 2026-09-20 to retire Firebase with no migration of the old
-- user base. Personal rows may exist without a school, so client_id becomes
-- nullable on user-owned tables.

alter table romalume.projects      alter column client_id drop not null;
alter table romalume.sources       alter column client_id drop not null;
alter table romalume.draft_versions alter column client_id drop not null;
alter table romalume.conversations alter column client_id drop not null;
alter table romalume.documents     alter column client_id drop not null;

-- projects: total tokens across ready sources (drives context_mode)
alter table romalume.projects
  add column if not exists total_source_tokens integer not null default 0;

-- sources: extracted text and page map live in Storage next to the file
alter table romalume.sources
  add column if not exists text_path text,
  add column if not exists pages_path text,
  add column if not exists paragraphs integer,
  add column if not exists map_kind text;

-- user_settings: everything the Firestore user document carried
alter table romalume.user_settings
  add column if not exists email text,
  add column if not exists display_name text,
  add column if not exists subscription_amount integer not null default 2000,
  add column if not exists subscription_current_period_end timestamptz,
  add column if not exists daily_usage_date date,
  add column if not exists daily_requests integer not null default 0,
  add column if not exists all_time_ai_cost_cents numeric(14,4) not null default 0,
  add column if not exists all_time_requests integer not null default 0,
  add column if not exists all_time_charity_cents numeric(14,4) not null default 0,
  add column if not exists email_preferences jsonb not null default '{}'::jsonb,
  add column if not exists chat_settings jsonb not null default '{}'::jsonb,
  add column if not exists unsubscribed boolean not null default false,
  add column if not exists profile_updated_at timestamptz,
  add column if not exists last_seen_at timestamptz;
create index if not exists user_settings_stripe_customer_idx
  on romalume.user_settings(stripe_customer_id);

-- conversations: Quick Chat current thread and archives share this table.
-- mode = 'current' is the live thread (one per user); archived rows keep
-- the legacy projectName grouping and a preview.
alter table romalume.conversations
  add column if not exists project_name text,
  add column if not exists preview text,
  add column if not exists archived_at timestamptz;
create unique index if not exists conversations_current_per_user
  on romalume.conversations(user_id) where mode = 'current' and project_id is null;

-- documents: Quick Chat uploads
alter table romalume.documents
  add column if not exists project_name text not null default 'General',
  add column if not exists indexing_error text;
create unique index if not exists documents_user_filename
  on romalume.documents(user_id, filename);

-- usage_logs: cost detail
alter table romalume.usage_logs
  add column if not exists routed_category text,
  add column if not exists search_docs boolean not null default false,
  add column if not exists cost_cents numeric(12,4) not null default 0;

-- signup rate limiting (was a Firestore collection keyed by date)
create table if not exists romalume.signup_rate_limits (
  bucket text primary key,
  count integer not null default 0,
  updated_at timestamptz not null default now()
);
alter table romalume.signup_rate_limits enable row level security;

-- monthly usage per user, derived
create or replace view romalume.user_monthly_usage as
  select user_id,
         to_char(created_at at time zone 'UTC', 'YYYY-MM') as month,
         sum(cost_cents) as total_ai_cost_cents,
         count(*) as total_requests,
         sum(coalesce(input_tokens,0)) as total_input_tokens,
         sum(coalesce(output_tokens,0)) as total_output_tokens
  from romalume.usage_logs
  group by user_id, to_char(created_at at time zone 'UTC', 'YYYY-MM');
grant select on romalume.user_monthly_usage to authenticated, service_role;

-- Storage bucket for uploads (private; served through the API)
insert into storage.buckets (id, name, public)
values ('romalume-sources', 'romalume-sources', false)
on conflict (id) do nothing;
