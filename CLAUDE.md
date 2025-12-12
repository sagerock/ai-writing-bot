# RomaLume - AI Writing Tool

## Project Overview
RomaLume is an AI-powered writing assistant with multi-model support (OpenAI, Anthropic Claude, Google Gemini, Cohere), document RAG search, and persistent user memory via mem0.

## Tech Stack
- **Frontend**: React 19 + Vite, React Router 7
- **Backend**: Python FastAPI with async support
- **Database**: Google Firebase (Firestore + Firebase Auth + Cloud Storage)
- **Vector DB**: Qdrant for document RAG search
- **Memory**: mem0 for persistent user memory

## Deployment

### Frontend (Firebase Hosting)
```bash
cd frontend
npm run build
npx firebase deploy --only hosting
```
- Hosted at: https://ai-writing-tool-bdebc.web.app
- Firebase project: `ai-writing-tool-bdebc`

### Backend (Railway)
- Auto-deploys from GitHub on push to `main` branch
- Repository: https://github.com/sagerock/ai-writing-bot
- Just push to GitHub and Railway will handle deployment:
```bash
git add .
git commit -m "your message"
git push
```

## Key Directories
- `/frontend/src/components/` - React components
- `/frontend/src/App.jsx` - Main app with routing
- `/frontend/src/App.css` - Global styles
- `/main.py` - FastAPI backend (all endpoints)

## Firestore Structure
```
users/{user_id}/
  ├── archives/          # Saved chat conversations (auto-saved + manual)
  ├── conversations/     # Current chat (current_chat document)
  └── documents/         # Uploaded file metadata
```

## mem0 (AI Memory)

mem0 provides persistent user memory that helps the AI personalize responses across conversations.

### How it works
- **Storage**: mem0 cloud service (separate from Firestore)
- **What's stored**: AI-extracted facts/insights about the user (not raw messages)
- **Example memories**: "User is attending law school", "User prefers concise responses"

### Firestore vs mem0
| Firestore | mem0 |
|-----------|------|
| Full chat transcripts | Extracted knowledge/facts |
| For viewing history | For AI personalization |
| `archives/` collection | mem0 cloud API |

### How mem0 is used in the app
1. **Auto-save**: After each AI response, the exchange is sent to mem0 (`save_to_mem0_background()` in main.py)
2. **Retrieval**: Before generating responses, relevant memories are fetched and injected as context
3. **User control**: Users can view/delete memories in Account page (`/user/memories` endpoints)

### API Endpoints
- `GET /user/memories` - Fetch all user memories
- `DELETE /user/memories/{memory_id}` - Delete specific memory
- `DELETE /user/memories` - Delete all memories
- `POST /save_memory` - Manually save conversation to mem0

## Common Commands
```bash
# Frontend development
cd frontend && npm run dev

# Build frontend
cd frontend && npm run build

# Deploy frontend to Firebase
npx firebase deploy --only hosting

# Query Firestore (from project root)
/home/sage/scripts/romalume/venv/bin/python -c "..."

# Push backend changes (triggers Railway deploy)
git push
```

## Environment Files
- `firebase_service_account.json` - Firebase Admin SDK credentials
- `.env` - API keys (OpenAI, Anthropic, Google, etc.)
