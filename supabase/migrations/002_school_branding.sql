-- Each school's RomaLume is branded as its Ask persona (Sage, 2026-09-20).
-- A CfA administrator opens "Iris", not RomaLume, so the writing workspace
-- and the email agent read as one thing. Applied to the shared project the
-- same day.

alter table romalume.school_settings
  add column if not exists brand_name text,
  add column if not exists persona_email text,
  add column if not exists logo_url text,
  add column if not exists accent_color text,
  add column if not exists tagline text;

comment on column romalume.school_settings.brand_name is
  'What the school sees as the product name, normally the Ask persona (e.g. Iris). Null falls back to RomaLume.';
comment on column romalume.school_settings.persona_email is
  'The Ask mailbox for this school, e.g. iris@ask.sagerock.com, so the UI can offer "email Iris".';

update romalume.school_settings
set brand_name = 'Iris',
    persona_email = 'iris@ask.sagerock.com',
    tagline = 'Center for Anthroposophy'
where client_id = '22500cd6-052a-42ff-a0cb-4f3ba9125dfd' and brand_name is null;
