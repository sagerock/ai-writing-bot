# RomaLume

RomaLume is a multi-model AI writing application with streaming chat, web search,
document retrieval, persistent conversation history, user profiles, subscriptions,
and administrative analytics.

## Live services

- Frontend: <https://romalume.com>
- Backend: <https://ai-writing-bot-production.up.railway.app>
- Backend health: <https://ai-writing-bot-production.up.railway.app/health>

## Stack

- React 19, Vite, and React Router
- FastAPI and Python 3.11
- Firebase Authentication, Firestore, Cloud Storage, and Hosting
- Qdrant with OpenAI embeddings for document retrieval
- Stripe subscriptions and SendGrid email

## Local setup

1. Create and activate a Python virtual environment.
2. Install backend dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and configure the required provider secrets.
4. Put a local Firebase Admin credential at `firebase_service_account.json`.
5. Copy `frontend/.env.example` to `frontend/.env` and fill in the public Firebase web configuration.
6. Install frontend dependencies with `cd frontend && npm ci`.

Run the services in separate terminals:

```bash
python -m uvicorn main:main_app --reload --host 127.0.0.1 --port 8000
cd frontend && npm run dev
```

The frontend is available at <http://localhost:5173>.

## Quality checks

```bash
python -m compileall -q main.py rag_service.py rag_identity.py message_storage.py cost_tracker.py
python -m unittest discover -s tests -v
cd frontend && npm run lint && npm run build
cd frontend && npm audit --omit=dev --audit-level=high
```

GitHub Actions runs these checks for pushes and pull requests.

## Deployment

The frontend is deployed through Firebase Hosting:

```bash
cd frontend
npm run build
npx firebase-tools@15.28.1 deploy --only hosting,firestore:rules,storage
```

The backend auto-deploys to Railway from `main`. Configure backend secrets in
Railway, including `FIREBASE_SERVICE_ACCOUNT_JSON`, provider API keys,
`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and a strong
`UNSUBSCRIBE_SECRET`. Set `TRUST_PROXY_HEADERS=true` only when the service is
behind a trusted proxy that overwrites forwarding headers.

Operational limits can be adjusted with `MAX_REQUEST_BYTES`,
`MAX_UPLOAD_BYTES`, `MAX_PDF_PAGES`, and `PAID_DAILY_MESSAGE_LIMIT`.

## Data model

User content is stored below `users/{user_id}` in Firestore:

- `archives`: saved conversations
- `conversations/current_chat`: bounded recent chat history
- `documents`: upload metadata
- `settings/profile`: the curated personalization profile
- `therapy_notes`: therapy-mode continuity notes

Document chunks are isolated by Firebase user ID in Qdrant. Billing fields on
the root user document are backend-owned; client-side Firestore writes to that
document are intentionally denied.

## Security notes

Never commit Firebase Admin credentials, `.env` files, Firebase Auth exports,
password hashes, or user exports. The ignored `firebase_service_account.json`
is for local development only. Use secret managers in deployed environments.

Firestore rules are not a development switch: use the Firebase emulator for
local rule testing instead of placing a real project in test mode.
Cloud Storage is also backend-only; deploy `frontend/storage.rules` with the
hosting and Firestore rules.

## Administration

Admin authorization uses the Firebase `admin: true` custom claim. The included
`set_admin.py` utility can assign the claim to an explicitly selected UID.

See `TROUBLESHOOTING.md`, `EMAIL_SETUP.md`, and `CREDIT_DEBUGGING_GUIDE.md` for
operational details.
