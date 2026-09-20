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

1. **Auth swap** (this branch). Backend accepts a Supabase access token when
   `AUTH_PROVIDER=supabase`; frontend logs in with supabase-js. Firebase stays
   the default until the frontend ships.
2. **Schema and stores.** `romalume` schema applied; `ProjectStore`,
   `message_storage`, settings, and usage move to Postgres behind the same
   interfaces; Storage bucket replaces the Firebase bucket.
3. **Persona branding.** Header, page title, login page, and empty states
   read `brand_name`, `logo_url`, `accent_color`, and `tagline` from the
   school row. "Email Iris" links to `persona_email`.
4. **School library.** Projects can belong to the school (`owner = client`).
   Uploads index into the school's Qdrant collection and register in
   `romalume.library_documents`. Iris's `search_content` points at that
   collection.
5. **Data move and cutover.** Twenty-nine Firebase users, one project, about a
   hundred documents. A one-time script maps Firebase UID to Supabase user by
   email and copies rows. Then Firebase is removed from the codebase.

## Environment variables (Railway, backend)

```
AUTH_PROVIDER=supabase            # or firebase (default until cutover)
SUPABASE_URL=https://ckloewflialohuvixmvd.supabase.co
SUPABASE_ANON_KEY=...             # used to validate user tokens
SUPABASE_SERVICE_KEY=...          # server-side reads and writes
```

Frontend (`frontend/.env`):

```
VITE_AUTH_PROVIDER=supabase
VITE_SUPABASE_URL=https://ckloewflialohuvixmvd.supabase.co
VITE_SUPABASE_ANON_KEY=...
```

## Migrations

SQL lives in `supabase/migrations/` in this repo and is applied to the shared
project with the Supabase connector or CLI. Never edit `public` tables from
here; they belong to the email tool's migration ledger.
