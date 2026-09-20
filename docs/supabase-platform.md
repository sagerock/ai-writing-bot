# RomaLume on Supabase: the school platform migration

Decided by Sage on 2026-09-20. RomaLume moves off Firebase (Auth, Firestore,
Storage) onto the shared SageRock Supabase project so that a school
administrator has one identity across RomaLume, the email tool, and Ask.

## Decisions

| Question | Decision |
|---|---|
| Supabase project | `ckloewflialohuvixmvd` (the email-tool project). Same `auth.users`, same `clients`, same `admin_users`. |
| Where RomaLume tables live | A dedicated `romalume` schema. Nothing in `public` changes. |
| What a "school" is | A row in `public.clients`. Center for Anthroposophy is `22500cd6-052a-42ff-a0cb-4f3ba9125dfd`. |
| What an "administrator" is | A row in `public.admin_users` with `role = 'client_admin'` and `client_id` set. Super admins see every school. |
| Row security | Every RomaLume table carries `client_id` and is protected by the existing `public.can_access_client(client_id)` function. Personal rows also carry `user_id`. |
| Document text for search | Stays in Qdrant (Railway "Qdrant General", the same instance Ask reads). Supabase holds the registry, never the chunks. |
| Uploaded files | Supabase Storage bucket `romalume-sources`, path `<client_id>/<project_id>/<source_id>/<filename>`. |
| Billing | Pilot schools are comped at the client level (`romalume.school_settings.comped`). Individual Stripe subscriptions remain for non-school users until the cutover. |
| Branding | Each school sees RomaLume under its Ask persona's name (`school_settings.brand_name`, e.g. Iris for CfA), with the persona's mailbox in `persona_email`. No school-facing RomaLume name. Decided 2026-09-20. |
| Audiences within a school | Library documents carry one tag: `staff`, `leadership`, `board`, `finance`. People hold a set per school in `romalume.member_audiences`. Enforced in Postgres by `romalume.can_read_audience()`; Qdrant carries the same tag and pre-filters. From `docs/cfa-pilot-brief.md` §1a. |
| School voice | `school_settings.voice_notes`, editable by leadership, derived from published content. |
| Pilot | Center for Anthroposophy. Karen Atkinson's individual Stripe subscription ends 2026-10-20 and her account is comped from 2026-09-20. |
| Deadline | Usable by CfA administrators before the AWSNA workshop, 2026-11-05 and 2026-11-06. |

## Why this shape

The email tool already has the identity model a school needs: a client, admins
scoped to that client, and a security-definer function every policy calls.
Reusing it means the same login works in mail.sagerock.com and RomaLume, and
Ask can look up the school's RomaLume library by the same `client_id` it
already uses for contacts. Building a second membership model in RomaLume
would have made "seamless" impossible.

## Phases

Sage changed the plan on 2026-09-20 from a gradual migration to a hard cut:
Firebase is retired outright and the old user base is not migrated. Only two
people were known to be using RomaLume (Rocky and Karen); anyone else can
email Sage. A full snapshot of Firestore (22 users, 27 MB) and Storage (130
objects) was taken first into the gitignored `.firebase-export/` folder.

1. **Done: schema.** Migrations 001-005 applied to the shared project.
2. **Done: backend on Postgres and Supabase Storage.** `db.py`, `user_store.py`,
   `project_store.py`, `blob_store.py`, `supabase_auth.py`. No Firebase code
   remains. Tokens are Supabase access tokens; admins are `super_admin` rows in
   `public.admin_users`.
3. **Done: frontend on Supabase Auth.** `src/auth/authClient.js` is the only
   auth surface. `/user/me` supplies role and school branding after login.
4. **Done: hosting on Cloudflare Pages.** Project `romalume` builds `frontend`
   from `sagerock/ai-writing-bot` on push to `main` (`romalume.pages.dev`).
5. **Done: cutover, 2026-09-20.** `main` deployed to Railway with the API
   connecting as the dedicated `romalume_app` role; `romalume.com` and `www`
   are proxied CNAMEs to `romalume.pages.dev`; the Firebase Hosting records
   and the Firebase credential on Railway are gone. The Firebase project
   itself still exists and can be deleted once the export is confirmed.
6. **Later: persona branding UI and the school library** (see
   `docs/cfa-pilot-brief.md`).

## Environment variables (Railway, backend)

```
SUPABASE_URL=https://ckloewflialohuvixmvd.supabase.co
SUPABASE_ANON_KEY=sb_publishable_...   # validates user tokens
SUPABASE_SERVICE_KEY=...               # server-side reads, writes, storage
DATABASE_URL=postgresql://...          # Supabase transaction pooler, port 6543
STORAGE_BUCKET=romalume-sources
```

Frontend (`frontend/.env`):

```
VITE_SUPABASE_URL=https://ckloewflialohuvixmvd.supabase.co
VITE_SUPABASE_ANON_KEY=sb_publishable_...
```

Cloudflare Pages holds the same two variables for production and preview.

## Migrations

SQL lives in `supabase/migrations/` in this repo and is applied to the shared
project with the Supabase connector or CLI. Never edit `public` tables from
here; they belong to the email tool's migration ledger.
