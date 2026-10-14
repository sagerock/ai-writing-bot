# RomaLume development notes

RomaLume is a React/FastAPI AI writing application. The API runs on Railway;
data lives in the shared SageRock Supabase project (`ckloewflialohuvixmvd`,
schema `romalume`) with Supabase Auth and Supabase Storage. Firebase was
retired on 2026-09-20; see `docs/supabase-platform.md`. The production API URL
is defined in `frontend/src/apiConfig.js`.

## Main areas

- `frontend/src/`: React application
- `main.py`: FastAPI routes and current service orchestration
- `db.py`: Postgres pool (`DATABASE_URL`, Supabase pooler)
- `user_store.py`: user settings, documents, conversations, usage, admin queries
- `project_store.py`: projects, sources, drafts, project chats
- `blob_store.py`: Supabase Storage (bucket `romalume-sources`)
- `supabase_auth.py`: token validation and school membership
- `supabase/migrations/`: schema history, applied to the shared project
- `rag_service.py`: Qdrant indexing and retrieval
- `rag_identity.py`: deterministic Qdrant point identity
- `cost_tracker.py`: model catalog and estimated provider costs
- `tests/`: backend unit tests

## Personalization

The curated profile lives in `romalume.user_settings.profile` (jsonb).

## Commands

```bash
# Frontend
cd frontend && npm ci
cd frontend && npm run dev
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build

# Backend verification
.venv/bin/python -m compileall -q main.py projects.py project_store.py user_store.py db.py blob_store.py supabase_auth.py project_context.py project_prompt.py project_templates.py source_extract.py llm_content.py rag_service.py rag_identity.py rag_chunks.py message_storage.py cost_tracker.py web_search.py
.venv/bin/python -m unittest discover -s tests -v

# Postgres integration tests run only when DATABASE_URL is set (they create and
# remove throwaway auth users in the shared project)
railway run -- .venv/bin/python -m unittest discover -s tests -p 'test_project*_postgres.py' -v

# Live smoke test of every catalog model (needs provider keys; Railway holds them)
railway run -- .venv/bin/python scripts/smoke_test_models.py
railway run -- .venv/bin/python scripts/smoke_test_models.py --project fixture

# Frontend deployment: Cloudflare Pages builds from the repo on push to main
# (project `romalume`, root `frontend`). No manual deploy step.
```

Pushing `main` triggers the Railway backend deployment and the Pages build. Do not push or deploy
without deliberately reviewing the diff and required environment variables.

## Sensitive files

Backend `.env`, frontend `.env`, `.firebase-export/` (the 2026-09-20 Firestore
and Storage snapshot), and user exports must remain untracked. Deployed
credentials belong in Railway and Supabase secret configuration.
