-- A school buys one plan that covers everyone (Sage, 2026-09-20 evening).
-- Members of a school with an active plan (or a comp) are fully entitled;
-- no per-person credits. Also a public slug so the login page can be
-- branded before anyone signs in (romalume.com/login?school=cfa).

alter table romalume.school_settings
  add column if not exists slug text unique,
  add column if not exists plan_status text not null default 'trial'
    check (plan_status in ('trial','active','paused','canceled')),
  add column if not exists plan_amount_cents integer,
  add column if not exists plan_started_at timestamptz,
  add column if not exists billing_note text;

-- Public branding lookup for the login page: no PII, safe for anon.
create or replace function romalume.public_branding(p_slug text)
returns table (slug text, name text, brand_name text, tagline text, logo_url text, accent_color text)
language sql security definer set search_path = public, romalume stable as $$
  select s.slug, c.name, s.brand_name, s.tagline, s.logo_url, s.accent_color
  from romalume.school_settings s join public.clients c on c.id = s.client_id
  where s.slug = lower(p_slug) and s.plan_status in ('trial','active')
$$;
grant execute on function romalume.public_branding(text) to romalume_app, anon, authenticated;

update romalume.school_settings
set slug = 'cfa',
    plan_status = 'active',
    plan_amount_cents = 145000,
    plan_started_at = '2026-09-20',
    billing_note = 'USD 1,450/month for Iris (Ask + writing workspace), agreed with Sage 2026-09-20; invoiced by SageRock.'
where client_id = '22500cd6-052a-42ff-a0cb-4f3ba9125dfd';
