import os
from datetime import datetime, timedelta
from typing import AsyncGenerator, List
import asyncio
from uuid import uuid4
import io
import sys
import json
import socket

os.environ["GRPC_DNS_RESOLVER"] = "native"  # Force gRPC to use system DNS

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Depends, Header, UploadFile, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from pypdf import PdfReader
from ddgs import DDGS

# RAG Service (lazy import to avoid startup failure if Qdrant unavailable)
def get_rag_service():
    """Get the RAG service singleton (lazy load)."""
    try:
        from rag_service import get_rag_service as _get_rag
        return _get_rag()
    except Exception as e:
        print(f"Warning: RAG service unavailable: {e}")
        return None
import firebase_admin
from firebase_admin import credentials, firestore, storage, auth as firebase_auth
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from langchain_anthropic import ChatAnthropic
from langchain_cohere import ChatCohere
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI
from google.cloud.firestore_v1.query import Query
from google.cloud.firestore_v1.transaction import Transaction
from google.cloud.firestore_v1.document import DocumentReference

# Email functionality (optional)
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    print("Warning: SendGrid not available. Email functionality will be disabled.")

load_dotenv()

# Set longer timeout for Firebase connections
socket.setdefaulttimeout(30)

# Firebase-related initialization
# Support both environment variable (for Render) and local file (for local dev)
firebase_creds = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
if firebase_creds:
    # Use environment variable (Render deployment)
    try:
        cred_dict = json.loads(firebase_creds)
        cred = credentials.Certificate(cred_dict)
        print("✓ Using Firebase credentials from environment variable")
    except json.JSONDecodeError as e:
        print(f"✗ Error parsing FIREBASE_SERVICE_ACCOUNT_JSON: {e}")
        raise
else:
    # Use local file (local development)
    try:
        cred = credentials.Certificate("firebase_service_account.json")
        print("✓ Using Firebase credentials from local file")
    except FileNotFoundError:
        print("✗ Error: firebase_service_account.json not found and FIREBASE_SERVICE_ACCOUNT_JSON env var not set")
        raise

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv('STORAGE_BUCKET')
    })
db = firestore.client()
bucket = storage.bucket()

main_app = FastAPI()

# --- Authentication ---
async def get_current_user(authorization: str = Header(...)):
    """Verifies Firebase ID token from Authorization header and returns user data."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme.")
    
    token = authorization.split("Bearer ")[1]
    
    try:
        # Verify the token against the Firebase project.
        decoded_token = id_token.verify_firebase_token(token, google_requests.Request())
        return decoded_token
    except ValueError as e:
        # Token is invalid
        raise HTTPException(status_code=401, detail=f"Invalid ID Token: {e}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Unauthorized: {e}")

# Allow CORS for frontend
main_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173", 
        "http://localhost:5173",
        "https://ai-writing-tool-bdebc.web.app",
        "https://romalume.com",
        "https://www.romalume.com"
    ], # Allow Vite dev server and deployed Firebase app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    history: List[Message]
    model: str
    search_web: bool = False
    search_docs: bool = False
    temperature: float = 0.7

class ArchiveRequest(BaseModel):
    history: List[Message]
    model: str
    archive_name: str | None = None
    project_name: str | None = "General"

class UserCredits(BaseModel):
    credits: int

class EmailPreferences(BaseModel):
    feature_updates: bool = True
    bug_fixes: bool = True
    pricing_changes: bool = True
    usage_tips: bool = True

class EmailRequest(BaseModel):
    subject: str
    content: str
    email_type: str  # "feature_updates", "bug_fixes", "pricing_changes", "usage_tips", "all"
    preview: bool = False

class UserChatSettings(BaseModel):
    simplified_mode: bool = True
    default_model: str = "gpt-5-mini-2025-08-07"
    default_temperature: float = 0.7
    always_ask_mode: bool = False

# Load API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

def get_llm(model_name: str, temperature: float = 0.7):
    """Factory function to get the LLM instance."""
    # Clamp temperature to the provider's supported range
    if model_name.startswith("gpt-5"):
        # GPT-5 models only support temperature = 1.0
        temperature = 1.0
    elif model_name.startswith("claude-") or model_name.startswith("command-") or model_name.startswith("gemini-") or model_name.startswith("sonar-"):
        # Anthropic, Cohere, Google, and Perplexity support 0.0-1.0
        temperature = max(0.0, min(1.0, float(temperature)))
    else:
        # OpenAI GPT-4, xAI, etc. support up to 2.0, but we'll cap at 1.5 for better results
        temperature = max(0.0, min(1.5, float(temperature)))

    if model_name.startswith("claude-"):
        return ChatAnthropic(
            model_name=model_name,
            temperature=temperature,
            max_tokens=4096,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    elif model_name.startswith(("gpt-", "o3-", "chatgpt-")):
        return ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=4096,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
    elif model_name.startswith("grok-"):
        return ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=4096,
            openai_api_key=os.getenv("XAI_API_KEY"),
            openai_api_base="https://api.x.ai/v1",
        )
    elif model_name.startswith("deepseek-"):
        return ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=4096,
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            openai_api_base="https://api.deepseek.com",
        )
    elif model_name.startswith("command-"):
        return ChatCohere(
            model=model_name,
            temperature=temperature,
            cohere_api_key=os.getenv("COHERE_API_KEY"),
            max_tokens=4096
        )
    elif model_name.startswith("gemini-"):
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            max_output_tokens=4096
        )
    elif model_name.startswith("sonar-"):
        # Perplexity uses OpenAI-compatible API
        return ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=4096,
            openai_api_key=os.getenv("PERPLEXITY_API_KEY"),
            openai_api_base="https://api.perplexity.ai",
        )
    else:
        raise ValueError(f"Unknown model provider for {model_name}")

def is_gpt5_model(model_name: str) -> bool:
    """Check if model is a GPT-5 family model that requires Responses API."""
    gpt5_models = ["gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-5-pro", "gpt-5.1"]
    return any(model_name.startswith(model) for model in gpt5_models)

async def generate_gpt5_response(req: ChatRequest, user_id: str):
    """Generate streaming response for GPT-5 models using Chat Completions API with GPT-5 parameters."""
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Convert history to messages format
    messages = []
    for msg in req.history:
        messages.append({
            "role": msg.role,
            "content": msg.content
        })

    # Handle web search for GPT-5 models
    if req.search_web and messages:
        # Find the last user message
        last_user_msg_index = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]['role'] == 'user':
                last_user_msg_index = i
                break

        if last_user_msg_index != -1:
            user_query = messages[last_user_msg_index]['content']
            search_snippets = []
            try:
                print(f"Starting DuckDuckGo search for GPT-5: {user_query[:100]}")
                ddgs = DDGS()
                results = list(ddgs.text(user_query, max_results=5))
                print(f"DuckDuckGo returned {len(results)} results")

                for result in results:
                    title = result.get('title', '')
                    body = result.get('body', '')
                    search_snippets.append(f"Result: {title} - {body}")

            except Exception as e:
                print(f"DuckDuckGo search failed for GPT-5: {type(e).__name__}: {e}")

            today = datetime.now().strftime('%B %d, %Y')
            if search_snippets:
                context = "\n\n".join(search_snippets)
                web_prompt = (
                    f"Today is {today}. The user has requested a web search. Here are the top search results. "
                    "Use this information to provide a timely and accurate answer.\n\n"
                    "--- BEGIN WEB SEARCH RESULTS ---\n"
                    f"{context}\n"
                    "--- END WEB SEARCH RESULTS ---\n\n"
                    f"Original Query: {user_query}"
                )
            else:
                web_prompt = (
                    f"Today is {today}. The user requested a web search but it could not be completed. "
                    "Please answer based on your knowledge and clearly note that you cannot provide real-time information.\n\n"
                    f"Original Query: {user_query}"
                )
            messages[last_user_msg_index]['content'] = web_prompt

    try:
        # GPT-5 models only support default temperature (1), so don't pass it
        response = await client.chat.completions.create(
            model=req.model,
            messages=messages,
            stream=True
        )

        # Stream the response
        full_response = ""
        async for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    full_response += delta.content
                    yield json.dumps(delta.content)

        print(f"GPT-5 response complete: {len(full_response)} chars")

    except Exception as e:
        error_msg = f"Error in GPT-5 response: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        yield json.dumps(f"ERROR: {str(e)}")

async def generate_chat_response(req: ChatRequest, user_id: str):
    user_ref = db.collection("users").document(user_id)

    # Use a transaction to safely read and update credits
    transaction = db.transaction()

    @firestore.transactional
    def check_and_update_credits(transaction: Transaction, user_ref: DocumentReference):
        user_snapshot = user_ref.get(transaction=transaction)

        if not user_snapshot.exists:
            initial_credits = 100
            transaction.set(user_ref, {
                "credits": initial_credits - 1,
                "credits_used": 1
            })
            return

        user_data = user_snapshot.to_dict()
        credits = user_data.get("credits", 0)

        if credits <= 0:
            raise HTTPException(status_code=402, detail="You have run out of credits.")

        transaction.update(user_ref, {
            "credits": firestore.Increment(-1),
            "credits_used": firestore.Increment(1)
        })

    try:
        check_and_update_credits(transaction, user_ref)
    except HTTPException as e:
        yield f"data: ERROR: {e.detail}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Log usage for analytics
    try:
        db.collection("usage_logs").add({
            "user_id": user_id,
            "model": req.model,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "date_key": datetime.now().strftime("%Y-%m-%d"),
            "search_web": req.search_web
        })
    except Exception as e:
        print(f"Failed to log usage: {e}")  # Don't fail the request if logging fails

    # Send a heartbeat immediately so the browser knows the stream is alive
    yield ": ping\n\n"

    # --- RAG: Search user's documents for relevant context (only if enabled) ---
    rag_context = ""
    if req.search_docs:
        try:
            rag = get_rag_service()
            if rag:
                # Find the last user message for search
                last_user_msg = None
                for msg in reversed(req.history):
                    if msg.role == 'user':
                        last_user_msg = msg.content
                        break

                if last_user_msg:
                    results = rag.search(user_id, last_user_msg, top_k=5, score_threshold=0.7)

                    if results:
                        context_parts = []
                        for r in results:
                            context_parts.append(f"[From: {r['filename']}]\n{r['chunk_text']}")
                        rag_context = "\n\n---\n\n".join(context_parts)
                        print(f"RAG found {len(results)} relevant chunks for user {user_id}")
        except Exception as e:
            print(f"RAG search failed (non-fatal): {e}")

    # Check if this is a GPT-5 model that requires Responses API
    if is_gpt5_model(req.model):
        # For GPT-5 models, inject RAG context into request history
        if rag_context:
            # Create a modified request with RAG context
            modified_history = list(req.history)
            for i in range(len(modified_history) - 1, -1, -1):
                if modified_history[i].role == 'user':
                    original_query = modified_history[i].content
                    modified_history[i] = Message(
                        role='user',
                        content=f"Based on the following relevant information from your documents:\n\n--- DOCUMENT CONTEXT ---\n{rag_context}\n--- END CONTEXT ---\n\nUser question: {original_query}"
                    )
                    break
            req = ChatRequest(
                history=modified_history,
                model=req.model,
                search_web=req.search_web,
                temperature=req.temperature
            )

        # Use the Responses API for GPT-5 models
        async for token in generate_gpt5_response(req, user_id):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"
        return

    llm = get_llm(req.model, req.temperature)
    history_messages = [message.dict() for message in req.history]

    # Inject RAG context into the conversation for non-GPT5 models
    if rag_context:
        for i in range(len(history_messages) - 1, -1, -1):
            if history_messages[i]['role'] == 'user':
                original_query = history_messages[i]['content']
                history_messages[i]['content'] = f"Based on the following relevant information from your documents:\n\n--- DOCUMENT CONTEXT ---\n{rag_context}\n--- END CONTEXT ---\n\nUser question: {original_query}"
                break

    if req.search_web:
        last_user_msg_index = -1
        for i in range(len(history_messages) - 1, -1, -1):
            if history_messages[i]['role'] == 'user':
                last_user_msg_index = i
                break

        if last_user_msg_index != -1:
            user_query = history_messages[last_user_msg_index]['content']
            search_snippets = []
            try:
                # Use DuckDuckGo for free web search
                print(f"Starting DuckDuckGo search for: {user_query[:100]}")
                ddgs = DDGS()
                results = list(ddgs.text(user_query, max_results=5))
                print(f"DuckDuckGo returned {len(results)} results")

                # Extract relevant information from the results
                for result in results:
                    title = result.get('title', '')
                    body = result.get('body', '')
                    search_snippets.append(f"Result: {title} - {body}")

            except Exception as e:
                print(f"DuckDuckGo search failed: {type(e).__name__}: {e}")

            # Always inject the date and search context, even if search failed
            today = datetime.now().strftime('%B %d, %Y')
            if search_snippets:
                context = "\n\n".join(search_snippets)
                web_prompt = (
                    f"Today is {today}. The user has requested a web search. Here are the top search results. "
                    "Use this information to provide a timely and accurate answer.\n\n"
                    "--- BEGIN WEB SEARCH RESULTS ---\n"
                    f"{context}\n"
                    "--- END WEB SEARCH RESULTS ---\n\n"
                    f"Original Query: {user_query}"
                )
            else:
                # Search failed, but still provide date context
                web_prompt = (
                    f"Today is {today}. The user requested a web search but it could not be completed. "
                    "Please answer based on your knowledge and clearly note that you cannot provide real-time information.\n\n"
                    f"Original Query: {user_query}"
                )
            history_messages[last_user_msg_index]['content'] = web_prompt

    llm_history = []
    for msg in history_messages:
        if msg.get('role') == 'context':
            llm_history.append({'role': 'user', 'content': msg.get('content', '')})
        else:
            llm_history.append(msg)

    response_accum = ""
    try:
        async for chunk in llm.astream(llm_history):
            token = chunk.content if hasattr(chunk, 'content') else str(chunk)
            response_accum += token
            # Use JSON encoding to safely transport tokens with special characters
            yield f"data: {json.dumps(token)}\n\n"

        final_history = history_messages + [{"role": "assistant", "content": response_accum}]
        save_conversation(user_id, final_history)

    except asyncio.CancelledError:
        print("Stream cancelled by client.")
    finally:
        yield "data: [DONE]\n\n"

@main_app.post("/chat_stream")
async def chat_stream_endpoint(
    req: ChatRequest,
    user: dict = Depends(get_current_user)
):
    user_id = user['user_id']
    
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    
    return StreamingResponse(
        generate_chat_response(req, user_id),
        media_type="text/event-stream",
        headers=headers
    )

@main_app.post("/archive")
async def archive_chat(req: ArchiveRequest, user: dict = Depends(get_current_user)):
    user_id = user['user_id']
    
    if not req.history:
        return JSONResponse(status_code=400, content={"error": "No chat history provided to archive."})
    
    project_name = req.project_name or "General"
    
    if req.archive_name:
        sanitized_name = "".join(c for c in req.archive_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        archive_id = f"{sanitized_name}.md"
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_id = f"chat_archive_{timestamp}.md"

    db.collection("users").document(user_id).collection("archives").document(archive_id).set({
        "projectName": project_name,
        "model": req.model,
        "messages": [msg.dict() for msg in req.history],
        "archivedAt": firestore.SERVER_TIMESTAMP
    })
        
    return JSONResponse(content={"message": f"Chat archived to {archive_id} in project {project_name}"})

@main_app.get("/archives")
async def get_archives(user: dict = Depends(get_current_user)):
    user_id = user['user_id']
    archives_ref = db.collection("users").document(user_id).collection("archives")
    archives = archives_ref.stream()

    project_archives = {}
    for archive in archives:
        data = archive.to_dict()
        project = data.get("projectName", "General")
        if project not in project_archives:
            project_archives[project] = []
        
        archived_at = data.get("archivedAt")
        if archived_at and hasattr(archived_at, 'isoformat'):
            archived_at = archived_at.isoformat()

        project_archives[project].append({
            "id": archive.id,
            "model": data.get("model"),
            "archivedAt": archived_at
        })

    return JSONResponse(content=project_archives)

@main_app.get("/projects")
async def get_projects(user: dict = Depends(get_current_user)):
    """Get all projects with their chats and documents organized together."""
    user_id = user['user_id']
    try:
        # Get archives
        archives_ref = db.collection("users").document(user_id).collection("archives")
        archives = archives_ref.stream()

        # Get documents
        docs_ref = db.collection("users").document(user_id).collection("documents")
        docs = docs_ref.stream()

        projects = {}

        # Process archives
        for archive in archives:
            data = archive.to_dict()
            project = data.get("projectName", "General")
            if project not in projects:
                projects[project] = {"chats": [], "documents": []}
            
            archived_at = data.get("archivedAt")
            if archived_at and hasattr(archived_at, 'isoformat'):
                archived_at = archived_at.isoformat()

            projects[project]["chats"].append({
                "id": archive.id,
                "model": data.get("model"),
                "archivedAt": archived_at,
                "type": "chat"
            })

        # Process documents
        for doc in docs:
            data = doc.to_dict()
            project = data.get("projectName", "General")
            if project not in projects:
                projects[project] = {"chats": [], "documents": []}
            
            uploaded_at = data.get("uploadedAt")
            if uploaded_at and hasattr(uploaded_at, 'isoformat'):
                uploaded_at = uploaded_at.isoformat()

            projects[project]["documents"].append({
                "filename": data.get("filename"),
                "contentType": data.get("contentType"),
                "size": data.get("size"),
                "uploadedAt": uploaded_at,
                "type": "document",
                "indexed": data.get("indexed", False),
                "chunkCount": data.get("chunkCount", 0),
                "indexingError": data.get("indexingError")
            })

        return JSONResponse(content=projects)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@main_app.get("/archive/{archive_id}")
async def get_archive_content(archive_id: str, user: dict = Depends(get_current_user)):
    user_id = user['user_id']
    try:
        doc_ref = db.collection("users").document(user_id).collection("archives").document(archive_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Archive not found")
        
        data = doc.to_dict()
        # Convert timestamp to string before sending
        archived_at = data.get("archivedAt")
        if archived_at and hasattr(archived_at, 'isoformat'):
             data['archivedAt'] = archived_at.isoformat()
            
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@main_app.get("/documents")
async def get_documents(user: dict = Depends(get_current_user)):
    user_id = user['user_id']
    try:
        docs_ref = db.collection("users").document(user_id).collection("documents").order_by("uploadedAt", direction=Query.DESCENDING)
        docs = docs_ref.stream()
        
        project_documents = {}
        for doc in docs:
            data = doc.to_dict()
            project = data.get("projectName", "General")  # Default to "General" for existing docs
            
            if project not in project_documents:
                project_documents[project] = []
            
            uploaded_at = data.get("uploadedAt")
            if uploaded_at and hasattr(uploaded_at, 'isoformat'):
                data['uploadedAt'] = uploaded_at.isoformat()
            
            project_documents[project].append(data)
        
        return JSONResponse(content=project_documents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@main_app.get("/history")
async def get_history(user: dict = Depends(get_current_user)):
    user_id = user['user_id']
    doc_ref = db.collection("users").document(user_id).collection("conversations").document("current_chat")
    doc = doc_ref.get()
    if doc.exists:
        return JSONResponse(content=doc.to_dict().get("messages", []))
    return JSONResponse(content=[])

@main_app.get("/documents/indexed")
async def get_indexed_documents(user: dict = Depends(get_current_user)):
    """Get list of documents that are indexed in the vector store."""
    user_id = user['user_id']
    try:
        rag = get_rag_service()
        if rag:
            indexed_docs = rag.get_user_indexed_documents(user_id)
            return JSONResponse(content={"documents": indexed_docs})
        return JSONResponse(content={"documents": [], "error": "RAG service unavailable"})
    except Exception as e:
        print(f"Failed to get indexed documents: {e}")
        return JSONResponse(content={"documents": [], "error": str(e)})

@main_app.get("/user/credits")
async def get_user_credits(user: dict = Depends(get_current_user)):
    user_id = user['user_id']
    user_ref = db.collection("users").document(user_id)
    user_snapshot = user_ref.get()

    if not user_snapshot.exists:
        # This case should ideally not happen if user has interacted at least once.
        # But as a fallback, we can say they have the initial free credits.
        return JSONResponse(content={"credits": 100})
    
    user_data = user_snapshot.to_dict()
    credits = user_data.get("credits", 0)
    return JSONResponse(content={"credits": credits})

# Background task to index document after quick upload
def index_document_background(user_id: str, filename: str, text: str, file_content: bytes, content_type: str):
    """Index document in Qdrant and save to Cloud Storage in the background."""
    try:
        # Upload to Cloud Storage
        file_path = f"{user_id}/documents/{filename}"
        blob = bucket.blob(file_path)
        blob.upload_from_string(file_content, content_type=content_type)
        print(f"Background: Uploaded {filename} to Cloud Storage")

        # Index in Qdrant
        indexed_chunks = 0
        indexing_error = None
        try:
            rag = get_rag_service()
            if rag and text:
                indexed_chunks = rag.index_document(user_id, filename, text, "General")
                print(f"Background: Indexed {filename} in Qdrant: {indexed_chunks} chunks")
        except Exception as e:
            print(f"Background: Failed to index in Qdrant: {e}")
            indexing_error = str(e)

        # Save metadata to Firestore
        doc_ref = db.collection("users").document(user_id).collection("documents").document(filename)
        doc_data = {
            "storagePath": file_path,
            "filename": filename,
            "contentType": content_type,
            "size": len(file_content),
            "projectName": "General",
            "uploadedAt": firestore.SERVER_TIMESTAMP,
            "indexed": indexed_chunks > 0,
            "chunkCount": indexed_chunks,
            "indexingError": indexing_error
        }
        doc_ref.set(doc_data)
        print(f"Background: Saved metadata for {filename}")

    except Exception as e:
        print(f"Background indexing error for {filename}: {e}")

# Quick file upload - extract text immediately, index in background
@main_app.post("/upload_quick")
async def upload_quick(background_tasks: BackgroundTasks, user: dict = Depends(get_current_user), file: UploadFile = File(...)):
    allowed_extensions = ('.md', '.txt', '.pdf')
    if not file.filename or not file.filename.endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail=f"Only {', '.join(allowed_extensions)} files are allowed.")

    try:
        file_content = await file.read()

        # Extract text
        text = ""
        if file.filename.lower().endswith(('.txt', '.md')):
            text = file_content.decode('utf-8')
        elif file.filename.lower().endswith('.pdf'):
            reader = PdfReader(io.BytesIO(file_content))
            text_pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(text_pages)

        # Truncate for chat context if too long (keep first 50k chars)
        display_text = text
        if len(display_text) > 50000:
            display_text = display_text[:50000] + "\n\n[... document truncated for length ...]"

        # Schedule background indexing (uses full text, not truncated)
        user_id = user['user_id']
        content_type = file.content_type or 'application/octet-stream'
        background_tasks.add_task(
            index_document_background,
            user_id,
            file.filename,
            text,  # Full text for indexing
            file_content,
            content_type
        )

        return JSONResponse(content={
            "filename": file.filename,
            "text": display_text,
            "size": len(file_content)
        })

    except Exception as e:
        import traceback, sys
        print("QUICK UPLOAD ERROR:", repr(e), file=sys.stderr)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

# File upload endpoint (full - saves to storage and indexes)
@main_app.post("/upload")
async def upload_file(user: dict = Depends(get_current_user), file: UploadFile = File(...), project_name: str = Form("General")):
    user_id = user['user_id']
    
    allowed_extensions = ('.md', '.txt', '.pdf')
    if not file.filename or not file.filename.endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail=f"Only {', '.join(allowed_extensions)} files are allowed.")

    try:
        # Define storage path
        file_path = f"{user_id}/documents/{file.filename}"
        blob = bucket.blob(file_path)
        
        # Upload the file
        file_content = await file.read()
        blob.upload_from_string(
            file_content,
            content_type=file.content_type
        )

        # --- Text Extraction ---
        text = ""
        try:
            if file.filename.lower().endswith(('.txt', '.md')):
                text = file_content.decode('utf-8')
            elif file.filename.lower().endswith('.pdf'):
                reader = PdfReader(io.BytesIO(file_content))
                text_pages = [page.extract_text() or "" for page in reader.pages]
                text = "\n".join(text_pages)
        except Exception as e:
            # If extraction fails, we still proceed, but the context will be empty.
            print(f"Failed to extract text from {file.filename}: {e}")

        # Index document in Qdrant for RAG
        indexed_chunks = 0
        indexing_error = None
        try:
            rag = get_rag_service()
            if rag and text:
                indexed_chunks = rag.index_document(user_id, file.filename, text, project_name)
                print(f"Indexed {file.filename} in Qdrant: {indexed_chunks} chunks")
        except Exception as e:
            print(f"Failed to index document in Qdrant: {e}")
            indexing_error = str(e)

        # Save metadata to Firestore
        doc_ref = db.collection("users").document(user_id).collection("documents").document(file.filename)
        doc_data = {
            "storagePath": file_path,
            "filename": file.filename,
            "contentType": file.content_type,
            "size": len(file_content),
            "projectName": project_name,
            "uploadedAt": firestore.SERVER_TIMESTAMP,
            "indexed": indexed_chunks > 0,
            "chunkCount": indexed_chunks,
            "indexingError": indexing_error
        }
        doc_ref.set(doc_data)

        # We can't get the server timestamp back immediately without another read,
        # so we'll approximate it for the response. The value in the DB will be accurate.
        doc_data['uploadedAt'] = datetime.now().isoformat()
        
        # This is the user-facing message that will be added to the chat
        display_message = f"File '{file.filename}' has been successfully uploaded and saved."
        context_message = {
            "role": "context",
            "content": text[:20000], # The actual text content for the LLM
            "display_text": display_message # The simple message for the UI
        }
        
        # Append a notification to the current conversation
        history = get_conversation(user_id)
        history.append(context_message)
        save_conversation(user_id, history)
        
        return JSONResponse(content={
            "message": f"File '{file.filename}' uploaded successfully.", 
            "document": doc_data,
            "context_message": context_message
        })

    except Exception as e:
        # Log the real exception so we can see it in the server logs
        import traceback, sys
        print("UPLOAD ERROR:", repr(e), file=sys.stderr)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to upload file to storage: {e}")

@main_app.get("/document/{filename}")
async def get_document_content(filename: str, user: dict = Depends(get_current_user)):
    """Return the text content of a stored document (txt, md, pdf)."""
    user_id = user['user_id']
    try:
        # Lookup the document metadata to confirm it exists and get storage path
        doc_ref = db.collection("users").document(user_id).collection("documents").document(filename)
        doc_snapshot = doc_ref.get()
        if not doc_snapshot.exists:
            raise HTTPException(status_code=404, detail="Document not found.")
        doc_data = doc_snapshot.to_dict()
        storage_path = doc_data["storagePath"]

        blob = bucket.blob(storage_path)
        if not blob.exists():
            raise HTTPException(status_code=404, detail="File not found in storage.")

        # Download and extract text depending on file type
        if filename.lower().endswith(('.txt', '.md')):
            text = blob.download_as_text()
        elif filename.lower().endswith('.pdf'):
            # For PDFs, download bytes then extract text with pypdf
            pdf_bytes = blob.download_as_bytes()
            reader = PdfReader(io.BytesIO(pdf_bytes))
            text_pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(text_pages)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type.")

        return JSONResponse(content={
            "filename": filename,
            "content": text[:20000]  # safeguard: limit to 20k chars
        })
    except HTTPException:
        raise
    except Exception as e:
        import traceback, sys
        print("GET DOCUMENT ERROR:", repr(e), file=sys.stderr)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to fetch document content.")

@main_app.delete("/archive/{archive_id}")
async def delete_archive(archive_id: str, user: dict = Depends(get_current_user)):
    user_id = user['user_id']
    try:
        doc_ref = db.collection("users").document(user_id).collection("archives").document(archive_id)
        
        # Check if the document exists before trying to delete
        if not doc_ref.get().exists:
            raise HTTPException(status_code=404, detail="Archive not found.")

        doc_ref.delete()
        return JSONResponse(content={"message": f"Archive '{archive_id}' deleted successfully."})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete archive: {e}")

@main_app.delete("/document/{filename}")
async def delete_document(filename: str, user: dict = Depends(get_current_user)):
    user_id = user['user_id']
    try:
        # First, delete the Firestore metadata document
        doc_ref = db.collection("users").document(user_id).collection("documents").document(filename)
        doc_snapshot = doc_ref.get()
        if not doc_snapshot.exists:
            raise HTTPException(status_code=404, detail="Document metadata not found.")

        doc_ref.delete()

        # Second, delete the actual file from Cloud Storage
        storage_path = f"{user_id}/documents/{filename}"
        blob = bucket.blob(storage_path)
        if blob.exists():
            blob.delete()

        # Third, delete from Qdrant (non-fatal if it fails)
        try:
            rag = get_rag_service()
            if rag:
                rag.delete_document(user_id, filename)
        except Exception as e:
            print(f"Failed to delete from Qdrant (non-fatal): {e}")

        return JSONResponse(content={"message": f"Document '{filename}' deleted successfully."})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {e}")

# --- Firestore Data Functions ---
def get_conversation(user_id: str) -> List[dict]:
    """Loads the current conversation history from Firestore."""
    doc_ref = db.collection("users").document(user_id).collection("conversations").document("current_chat")
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get("messages", [])
    return []

def save_conversation(user_id: str, messages: List[dict]):
    """Saves the entire conversation history to Firestore."""
    doc_ref = db.collection("users").document(user_id).collection("conversations").document("current_chat")
    doc_ref.set({"messages": messages, "updatedAt": firestore.SERVER_TIMESTAMP})

async def get_current_admin_user(user: dict = Depends(get_current_user)):
    """Verifies that the current user is an admin."""
    # The 'admin' claim is set by the set_admin.py script
    # and is part of the user's ID token.
    if not user.get("admin"):
        raise HTTPException(status_code=403, detail="Forbidden: User does not have admin privileges.")
    return user

class CreditUpdate(BaseModel):
    amount: int

class RoleUpdate(BaseModel):
    is_admin: bool

@main_app.get("/admin/users", response_model=List[dict])
async def list_users(_: dict = Depends(get_current_admin_user)):
    """Lists all users from Firebase Auth and merges with Firestore data."""
    try:
        # Get all users from Firebase Authentication
        auth_users = firebase_auth.list_users().iterate_all()
        
        users_list = []
        for user in auth_users:
            user_data = {
                "uid": user.uid,
                "email": user.email,
                "displayName": user.display_name or "",
                "isAdmin": user.custom_claims.get("admin", False) if user.custom_claims else False,
                "credits": 0,  # Default credits
                "credits_used": 0 # Default used credits
            }
            
            # Fetch credit data from Firestore
            user_doc = db.collection("users").document(user.uid).get()
            if user_doc.exists:
                firestore_data = user_doc.to_dict()
                user_data["credits"] = firestore_data.get("credits", 0)
                user_data["credits_used"] = firestore_data.get("credits_used", 0)
                
            users_list.append(user_data)
            
        return users_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while fetching users: {e}")

@main_app.post("/admin/users/{user_id}/credits")
async def update_user_credits(user_id: str, credit_update: CreditUpdate, _: dict = Depends(get_current_admin_user)):
    try:
        user_ref = db.collection("users").document(user_id)
        user_ref.set({"credits": firestore.Increment(credit_update.amount)}, merge=True)
        return JSONResponse(content={"message": f"Credits for user {user_id} updated successfully."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@main_app.post("/admin/users/{user_id}/role")
async def update_user_role(user_id: str, role_update: RoleUpdate, _: dict = Depends(get_current_admin_user)):
    try:
        firebase_auth.set_custom_user_claims(user_id, {"admin": role_update.is_admin})
        return {"message": f"User role updated successfully. Admin: {role_update.is_admin}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@main_app.get("/admin/debug/user/{user_id}/credits")
async def debug_user_credits(user_id: str, _: dict = Depends(get_current_admin_user)):
    """
    Debug endpoint for investigating credit issues for a specific user.
    Returns detailed information about the user's credit status.
    """
    try:
        # Get user data from Firestore
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        # Get user data from Firebase Auth
        auth_user_data = None
        try:
            auth_user = firebase_auth.get_user(user_id)
            auth_user_data = {
                "email": auth_user.email,
                "display_name": auth_user.display_name,
                "email_verified": auth_user.email_verified,
                "disabled": auth_user.disabled,
                "custom_claims": auth_user.custom_claims
            }
        except Exception as auth_error:
            print(f"Auth error for user {user_id}: {auth_error}")

        # Simulate the credit check logic
        transaction = db.transaction()
        
        @firestore.transactional
        def simulate_credit_check(transaction: Transaction, user_ref):
            user_snapshot = user_ref.get(transaction=transaction)
            
            if not user_snapshot.exists:
                return {
                    "status": "new_user",
                    "would_get_initial_credits": True,
                    "initial_credits_amount": 100
                }
            
            user_data = user_snapshot.to_dict()
            credits = user_data.get("credits", 0)
            
            return {
                "status": "existing_user",
                "current_credits": credits,
                "credits_type": type(credits).__name__,
                "would_pass_check": credits > 0,
                "credits_after_use": credits - 1 if credits > 0 else credits
            }
        
        credit_simulation = simulate_credit_check(transaction, user_ref)
        
        # Prepare response
        debug_info = {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "firebase_auth": {
                "exists": auth_user_data is not None,
                "data": auth_user_data
            },
            "firestore": {
                "document_exists": user_doc.exists,
                "raw_data": user_doc.to_dict() if user_doc.exists else None
            },
            "credit_simulation": credit_simulation,
            "diagnosis": {
                "likely_issue": None,
                "recommendations": []
            }
        }
        
        # Determine likely issues and recommendations
        if not user_doc.exists:
            debug_info["diagnosis"]["likely_issue"] = "User document doesn't exist in Firestore"
            debug_info["diagnosis"]["recommendations"] = [
                "User should make their first request to create the document with initial 100 credits",
                "If they have made requests, there may be a database connectivity issue"
            ]
        elif not credit_simulation.get("would_pass_check", True):
            debug_info["diagnosis"]["likely_issue"] = "User has 0 or negative credits"
            debug_info["diagnosis"]["recommendations"] = [
                "Add credits using the admin panel",
                f"Current credits: {credit_simulation.get('current_credits', 'unknown')}"
            ]
        else:
            debug_info["diagnosis"]["likely_issue"] = "Credits appear normal"
            debug_info["diagnosis"]["recommendations"] = [
                "Check client-side issues (browser cache, authentication)",
                "Verify correct user ID is being used",
                "Check API logs for other error messages"
            ]

        return JSONResponse(content=debug_info)
        
    except Exception as e:
        print(f"Debug credit error: {e}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")

@main_app.get("/admin/debug/credits/summary")
async def debug_credits_summary(_: dict = Depends(get_current_admin_user)):
    """
    Debug endpoint that provides a summary of all users' credit status.
    Useful for identifying widespread credit issues.
    """
    try:
        # Get all users from Firebase Auth (limit to 100 for performance)
        auth_users = firebase_auth.list_users(max_results=100).users
        
        summary = {
            "total_users_checked": len(auth_users),
            "users_with_credits": 0,
            "users_out_of_credits": 0,
            "users_no_firestore_data": 0,
            "users_with_errors": 0,
            "timestamp": datetime.now().isoformat(),
            "sample_issues": []
        }
        
        for user in auth_users:
            try:
                user_ref = db.collection("users").document(user.uid)
                user_doc = user_ref.get()
                
                if not user_doc.exists:
                    summary["users_no_firestore_data"] += 1
                else:
                    user_data = user_doc.to_dict()
                    credits = user_data.get("credits", 0)
                    
                    if isinstance(credits, (int, float)):
                        if credits > 0:
                            summary["users_with_credits"] += 1
                        else:
                            summary["users_out_of_credits"] += 1
                            if len(summary["sample_issues"]) < 5:
                                summary["sample_issues"].append({
                                    "user_id": user.uid,
                                    "email": user.email,
                                    "credits": credits,
                                    "issue": "out_of_credits"
                                })
                    else:
                        summary["users_with_errors"] += 1
                        if len(summary["sample_issues"]) < 5:
                            summary["sample_issues"].append({
                                "user_id": user.uid,
                                "email": user.email,
                                "credits": credits,
                                "issue": "invalid_credits_type"
                            })
                            
            except Exception as user_error:
                summary["users_with_errors"] += 1
                print(f"Error checking user {user.uid}: {user_error}")
        
        return JSONResponse(content=summary)
        
    except Exception as e:
        print(f"Debug credits summary error: {e}")
        raise HTTPException(status_code=500, detail=f"Debug summary failed: {str(e)}")

@main_app.post("/admin/debug/user/{user_id}/fix-credits")
async def fix_user_credits(user_id: str, credit_amount: int, _: dict = Depends(get_current_admin_user)):
    """
    Emergency endpoint to fix a user's credits.
    This bypasses the normal credit update endpoint to directly set credits.
    """
    try:
        if credit_amount < 0:
            raise HTTPException(status_code=400, detail="Credit amount must be non-negative")
        
        user_ref = db.collection("users").document(user_id)
        user_ref.set({
            "credits": credit_amount,
            "credits_fixed_at": firestore.SERVER_TIMESTAMP,
            "credits_fixed_by": "admin_debug_endpoint"
        }, merge=True)
        
        # Verify the fix
        updated_doc = user_ref.get()
        if updated_doc.exists:
            updated_credits = updated_doc.to_dict().get("credits")
            return JSONResponse(content={
                "message": f"Credits fixed successfully",
                "user_id": user_id,
                "new_credits": updated_credits,
                "timestamp": datetime.now().isoformat()
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to verify credit fix")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Fix credits error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fix credits: {str(e)}")

# --- Analytics Endpoints ---

# Cost estimates per request (in dollars, based on ~2K tokens average)
MODEL_COSTS = {
    "gpt-5-nano": 0.002,
    "gpt-5-mini": 0.006,
    "gpt-5-2025": 0.02,
    "gpt-5-pro": 0.06,
    "gpt-5.1": 0.03,
    "gpt-4.1-nano": 0.002,
    "gpt-4.1-mini": 0.004,
    "gpt-4.1-2025": 0.02,
    "claude-sonnet": 0.03,
    "claude-opus": 0.15,
    "gemini-2.5-flash": 0.002,
    "gemini-2.5-pro": 0.014,
    "sonar-pro": 0.01,
}

def estimate_cost(model: str, request_count: int) -> float:
    """Estimate cost for a model based on request count."""
    for prefix, cost in MODEL_COSTS.items():
        if model.startswith(prefix):
            return request_count * cost
    return 0.0  # Unknown model

@main_app.get("/admin/analytics/overview")
async def get_analytics_overview(_: dict = Depends(get_current_admin_user)):
    """Get high-level usage statistics."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        usage_logs = db.collection("usage_logs")

        # Get all logs (for total count)
        all_logs = list(usage_logs.stream())
        total_requests = len(all_logs)

        # Count by date ranges
        today_count = 0
        week_count = 0
        month_count = 0
        model_counts = {}
        unique_users_today = set()

        for log in all_logs:
            data = log.to_dict()
            date_key = data.get("date_key", "")
            model = data.get("model", "unknown")
            user_id = data.get("user_id", "")

            # Count by model
            model_counts[model] = model_counts.get(model, 0) + 1

            if date_key == today:
                today_count += 1
                unique_users_today.add(user_id)
            if date_key >= week_ago:
                week_count += 1
            if date_key >= month_ago:
                month_count += 1

        # Find top model
        top_model = max(model_counts, key=model_counts.get) if model_counts else "N/A"
        top_model_count = model_counts.get(top_model, 0)

        return {
            "total_requests_all_time": total_requests,
            "total_requests_today": today_count,
            "total_requests_this_week": week_count,
            "total_requests_this_month": month_count,
            "active_users_today": len(unique_users_today),
            "top_model": top_model,
            "top_model_requests": top_model_count
        }
    except Exception as e:
        print(f"Analytics overview error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")

@main_app.get("/admin/analytics/daily")
async def get_daily_analytics(
    days: int = 30,
    _: dict = Depends(get_current_admin_user)
):
    """Get daily request counts for the past N days. Use days=0 for all time."""
    try:
        usage_logs = db.collection("usage_logs")

        if days == 0:
            # All time - no date filter
            logs = list(usage_logs.stream())
        else:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            logs = list(usage_logs.where("date_key", ">=", start_date).stream())

        # Aggregate by date
        daily_data = {}
        for log in logs:
            data = log.to_dict()
            date_key = data.get("date_key", "")
            model = data.get("model", "unknown")

            if date_key not in daily_data:
                daily_data[date_key] = {"date": date_key, "total_requests": 0, "requests_by_model": {}}

            daily_data[date_key]["total_requests"] += 1
            daily_data[date_key]["requests_by_model"][model] = daily_data[date_key]["requests_by_model"].get(model, 0) + 1

        # Sort by date
        result = sorted(daily_data.values(), key=lambda x: x["date"])
        return result
    except Exception as e:
        print(f"Daily analytics error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get daily analytics: {str(e)}")

@main_app.get("/admin/analytics/models")
async def get_model_analytics(
    days: int = 30,
    _: dict = Depends(get_current_admin_user)
):
    """Get usage breakdown by model with cost estimates. Use days=0 for all time."""
    try:
        usage_logs = db.collection("usage_logs")

        if days == 0:
            # All time - no date filter
            logs = list(usage_logs.stream())
        else:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            logs = list(usage_logs.where("date_key", ">=", start_date).stream())

        # Aggregate by model
        model_counts = {}
        total_requests = 0

        for log in logs:
            data = log.to_dict()
            model = data.get("model", "unknown")
            model_counts[model] = model_counts.get(model, 0) + 1
            total_requests += 1

        # Build result with percentages and costs
        result = []
        for model, count in sorted(model_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_requests * 100) if total_requests > 0 else 0
            estimated_cost = estimate_cost(model, count)
            result.append({
                "model": model,
                "total_requests": count,
                "percentage": round(percentage, 1),
                "estimated_cost": round(estimated_cost, 2)
            })

        return result
    except Exception as e:
        print(f"Model analytics error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get model analytics: {str(e)}")

# --- Email Functionality ---
def send_email(to_email: str, subject: str, html_content: str):
    """Send email using SendGrid."""
    if not SENDGRID_AVAILABLE:
        print(f"Email not sent to {to_email}: SendGrid not configured")
        return False
        
    try:
        sg = SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))
        message = Mail(
            from_email=os.getenv('FROM_EMAIL', 'noreply@romalume.com'),
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        response = sg.send(message)
        return response.status_code == 202
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False

def get_email_template(email_type: str, subject: str, content: str, user_id: str = None) -> str:
    """Generate HTML email template."""
    unsubscribe_links = ""
    if user_id:
        unsubscribe_links = f"""
            <p style="font-size: 11px; color: #999; margin-top: 15px;">
                <a href="https://ai-writing-bot-backend.onrender.com/unsubscribe/{user_id}?email_type={email_type}">Unsubscribe from {get_type_label(email_type)}</a> | 
                <a href="https://ai-writing-bot-backend.onrender.com/unsubscribe/{user_id}">Unsubscribe from all emails</a>
            </p>
        """
    
    base_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{subject}</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
            .cta {{ background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
            .type-badge {{ display: inline-block; padding: 5px 10px; border-radius: 15px; font-size: 12px; font-weight: bold; margin-bottom: 15px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>RomaLume</h1>
            <p>AI Writing Assistant</p>
        </div>
        <div class="content">
            <div class="type-badge" style="background: {get_type_color(email_type)}; color: white;">
                {get_type_label(email_type)}
            </div>
            {content}
            <br><br>
            <a href="https://ai-writing-tool-bdebc.web.app" class="cta">Open RomaLume</a>
        </div>
        <div class="footer">
            <p>You're receiving this email because you're a RomaLume user.</p>
            <p><a href="https://ai-writing-tool-bdebc.web.app/account">Manage Email Preferences</a></p>
            {unsubscribe_links}
        </div>
    </body>
    </html>
    """
    return base_template

def get_type_color(email_type: str) -> str:
    """Get color for email type badge."""
    colors = {
        "feature_updates": "#28a745",
        "bug_fixes": "#ffc107", 
        "pricing_changes": "#dc3545",
        "usage_tips": "#17a2b8",
        "all": "#6c757d"
    }
    return colors.get(email_type, "#6c757d")

def get_type_label(email_type: str) -> str:
    """Get label for email type badge."""
    labels = {
        "feature_updates": "🚀 New Feature",
        "bug_fixes": "🐛 Bug Fix", 
        "pricing_changes": "💰 Pricing Update",
        "usage_tips": "💡 Usage Tip",
        "all": "📢 Announcement"
    }
    return labels.get(email_type, "📢 Announcement")

async def get_users_for_email(email_type: str) -> List[dict]:
    """Get users who should receive emails of this type."""
    users_ref = db.collection("users")
    users = []
    
    # Get all users from Firebase Auth
    try:
        page = firebase_auth.list_users()
        for user in page.users:
            # Get user preferences from Firestore
            user_doc = users_ref.document(user.uid).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                email_prefs = user_data.get("email_preferences", {})
                
                # Check if user wants this type of email
                if email_type == "all" or email_prefs.get(email_type, True):
                    users.append({
                        "uid": user.uid,
                        "email": user.email,
                        "display_name": user.display_name or user.email
                    })
            else:
                # New user without preferences, default to True
                users.append({
                    "uid": user.uid,
                    "email": user.email,
                    "display_name": user.display_name or user.email
                })
    except Exception as e:
        print(f"Error getting users: {e}")
    
    return users

# --- Email Endpoints ---
@main_app.get("/admin/email/preview")
async def preview_email_recipients(email_type: str, _: dict = Depends(get_current_admin_user)):
    """Preview which users would receive an email of this type."""
    users = await get_users_for_email(email_type)
    return {
        "email_type": email_type,
        "recipient_count": len(users),
        "recipients": users[:10] if len(users) > 10 else users  # Show first 10 for preview
    }

@main_app.post("/admin/email/send")
async def send_bulk_email(email_request: EmailRequest, _: dict = Depends(get_current_admin_user)):
    """Send email to users based on type and preferences."""
    if email_request.preview:
        # Just return preview without sending
        users = await get_users_for_email(email_request.email_type)
        return {
            "preview": True,
            "recipient_count": len(users),
            "recipients": users[:10] if len(users) > 10 else users
        }
    
    # Get recipients
    users = await get_users_for_email(email_request.email_type)
    if not users:
        raise HTTPException(status_code=400, detail="No recipients found for this email type")
    
    # Send emails
    success_count = 0
    failed_emails = []
    
    for user in users:
        try:
            # Generate personalized email template for each user
            html_content = get_email_template(email_request.email_type, email_request.subject, email_request.content, user["uid"])
            
            success = send_email(user["email"], email_request.subject, html_content)
            if success:
                success_count += 1
            else:
                failed_emails.append(user["email"])
        except Exception as e:
            failed_emails.append(user["email"])
            print(f"Failed to send email to {user['email']}: {e}")
    
    return {
        "message": f"Email sent to {success_count} out of {len(users)} recipients",
        "success_count": success_count,
        "total_recipients": len(users),
        "failed_emails": failed_emails
    }

@main_app.get("/user/email-preferences")
async def get_user_email_preferences(user: dict = Depends(get_current_user)):
    """Get user's email preferences."""
    user_ref = db.collection("users").document(user["user_id"])
    user_doc = user_ref.get()
    
    if user_doc.exists:
        user_data = user_doc.to_dict()
        email_prefs = user_data.get("email_preferences", {
            "feature_updates": True,
            "bug_fixes": True,
            "pricing_changes": True,
            "usage_tips": True
        })
        return email_prefs
    else:
        # Return default preferences for new users
        return {
            "feature_updates": True,
            "bug_fixes": True,
            "pricing_changes": True,
            "usage_tips": True
        }

@main_app.post("/user/email-preferences")
async def update_user_email_preferences(
    preferences: EmailPreferences, 
    user: dict = Depends(get_current_user)
):
    """Update user's email preferences."""
    user_ref = db.collection("users").document(user["user_id"])
    
    # Update or create user document with email preferences
    user_ref.set({
        "email_preferences": {
            "feature_updates": preferences.feature_updates,
            "bug_fixes": preferences.bug_fixes,
            "pricing_changes": preferences.pricing_changes,
            "usage_tips": preferences.usage_tips
        }
    }, merge=True)
    
    return {"message": "Email preferences updated successfully"}

@main_app.get("/user/chat-settings")
async def get_user_chat_settings(user: dict = Depends(get_current_user)):
    """Get user's chat settings (simplified mode, default model, etc.)."""
    user_id = user["user_id"]
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()

    # Default settings for new users
    default_settings = {
        "simplified_mode": True,
        "default_model": "gpt-5-mini-2025-08-07",
        "default_temperature": 0.7,
        "always_ask_mode": False
    }

    if user_doc.exists:
        user_data = user_doc.to_dict()
        return user_data.get("chat_settings", default_settings)
    return default_settings

@main_app.post("/user/chat-settings")
async def update_user_chat_settings(
    settings: UserChatSettings,
    user: dict = Depends(get_current_user)
):
    """Update user's chat settings."""
    user_id = user["user_id"]
    user_ref = db.collection("users").document(user_id)

    user_ref.set({
        "chat_settings": {
            "simplified_mode": settings.simplified_mode,
            "default_model": settings.default_model,
            "default_temperature": settings.default_temperature,
            "always_ask_mode": settings.always_ask_mode
        }
    }, merge=True)

    return {"message": "Chat settings updated successfully"}

@main_app.get("/unsubscribe/{user_id}")
async def unsubscribe_user(user_id: str, email_type: str = None):
    """Unsubscribe user from specific email type or all emails."""
    try:
        # Get user from Firebase Auth
        user = firebase_auth.get_user(user_id)
        user_ref = db.collection("users").document(user_id)
        
        # Get current preferences
        user_doc = user_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            email_prefs = user_data.get("email_preferences", {
                "feature_updates": True,
                "bug_fixes": True,
                "pricing_changes": True,
                "usage_tips": True
            })
        else:
            email_prefs = {
                "feature_updates": True,
                "bug_fixes": True,
                "pricing_changes": True,
                "usage_tips": True
            }
        
        # Update preferences based on email_type
        if email_type and email_type in email_prefs:
            # Unsubscribe from specific type
            email_prefs[email_type] = False
            message = f"Unsubscribed from {email_type} emails"
        else:
            # Unsubscribe from all emails
            for key in email_prefs:
                email_prefs[key] = False
            message = "Unsubscribed from all emails"
        
        # Save updated preferences
        user_ref.set({
            "email_preferences": email_prefs
        }, merge=True)
        
        # Return HTML page with confirmation
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Unsubscribed - RomaLume</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; text-align: center; }}
                .container {{ background: #f9f9f9; padding: 30px; border-radius: 10px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; margin: -30px -30px 30px -30px; }}
                .success {{ color: #28a745; font-size: 18px; margin: 20px 0; }}
                .info {{ background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .cta {{ background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
                .preferences {{ text-align: left; background: white; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                .preference-item {{ margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 3px; }}
                .enabled {{ border-left: 4px solid #28a745; }}
                .disabled {{ border-left: 4px solid #dc3545; opacity: 0.6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>RomaLume</h1>
                    <p>Email Preferences Updated</p>
                </div>
                
                <div class="success">✅ {message}</div>
                
                <div class="info">
                    <p><strong>Current Email Preferences:</strong></p>
                </div>
                
                <div class="preferences">
                    <div class="preference-item {'enabled' if email_prefs['feature_updates'] else 'disabled'}">
                        🚀 <strong>New Features & Updates:</strong> {'Enabled' if email_prefs['feature_updates'] else 'Disabled'}
                    </div>
                    <div class="preference-item {'enabled' if email_prefs['bug_fixes'] else 'disabled'}">
                        🐛 <strong>Bug Fixes & Improvements:</strong> {'Enabled' if email_prefs['bug_fixes'] else 'Disabled'}
                    </div>
                    <div class="preference-item {'enabled' if email_prefs['pricing_changes'] else 'disabled'}">
                        💰 <strong>Pricing & Plan Changes:</strong> {'Enabled' if email_prefs['pricing_changes'] else 'Disabled'}
                    </div>
                    <div class="preference-item {'enabled' if email_prefs['usage_tips'] else 'disabled'}">
                        💡 <strong>Usage Tips & Best Practices:</strong> {'Enabled' if email_prefs['usage_tips'] else 'Disabled'}
                    </div>
                </div>
                
                <p>You can change these preferences anytime in your account settings.</p>
                
                <a href="https://ai-writing-tool-bdebc.web.app/account" class="cta">Manage Email Preferences</a>
                
                <p style="margin-top: 30px; font-size: 12px; color: #666;">
                    If you have any questions, please contact us at support@romalume.com
                </p>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Error - RomaLume</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .error {{ color: #dc3545; }}
            </style>
        </head>
        <body>
            <h1>Error</h1>
            <p class="error">Unable to process unsubscribe request.</p>
            <p>Please contact support@romalume.com for assistance.</p>
        </body>
        </html>
        """)

# Static files should be mounted last, after all other routes are defined.
main_app.mount("/", StaticFiles(directory="static", html=True), name="static")

@main_app.get("/")
def root():
    return FileResponse('static/index.html')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:main_app", host="127.0.0.1", port=8000, reload=True)