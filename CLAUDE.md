# RomaLume development notes

RomaLume is a React/FastAPI AI writing application deployed to Firebase Hosting
and Railway. The production API URL is defined in `frontend/src/apiConfig.js`.

## Main areas

- `frontend/src/`: React application
- `main.py`: FastAPI routes and current service orchestration
- `rag_service.py`: Qdrant indexing and retrieval
- `rag_identity.py`: deterministic Qdrant point identity
- `cost_tracker.py`: model catalog and estimated provider costs
- `frontend/firestore.rules`: browser access boundary
- `tests/`: backend unit tests

## Personalization

The former mem0 integration has been replaced by a Firestore-backed curated
profile at `users/{user_id}/settings/profile`.

## Commands

```bash
# Frontend
cd frontend && npm ci
cd frontend && npm run dev
cd frontend && npm run lint
cd frontend && npm run build

# Backend verification
python -m compileall -q main.py projects.py project_store.py source_extract.py llm_content.py rag_service.py rag_identity.py message_storage.py cost_tracker.py
python -m unittest discover -s tests -v

# Firestore integration tests (emulator port 8082)
cd frontend && npx firebase-tools@15.28.1 emulators:exec --only firestore --project demo-romalume "PYTHONPATH=.. ../.venv/bin/python -m unittest discover -s ../tests -p 'test_projects_firestore.py' -v"

# Live smoke test of every catalog model (needs provider keys; Railway holds them)
railway run -- python scripts/smoke_test_models.py

# Frontend deployment
cd frontend && npx firebase-tools@15.28.1 deploy --only hosting,firestore:rules,storage
```

Pushing `main` triggers the Railway backend deployment. Do not push or deploy
without deliberately reviewing the diff and required environment variables.

## Sensitive files

`firebase_service_account.json`, backend `.env`, frontend `.env`, Firebase Auth
exports, and user exports must remain untracked. Deployed credentials belong in
Railway/Firebase secret configuration.
