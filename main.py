import os
from datetime import datetime
from typing import AsyncGenerator, List
import asyncio
from uuid import uuid4
import io

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Depends, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from pypdf import PdfReader
from duckduckgo_search import DDGS
import firebase_admin
from firebase_admin import credentials, firestore, storage, auth as firebase_auth
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from langchain_anthropic import ChatAnthropic
from langchain_cohere import ChatCohere
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from google.cloud.firestore_v1.query import Query

load_dotenv()

# Firebase-related initialization
cred = credentials.Certificate("firebase_service_account.json")
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
    allow_origins=["*"], # In production, restrict this to your frontend domain
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

class ArchiveRequest(BaseModel):
    history: List[Message]
    model: str
    archive_name: str | None = None
    project_name: str | None = "General"

# Load API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

def get_llm(model_name: str):
    """Factory function to get the LLM instance."""
    if model_name.startswith(("gpt-", "o3-", "chatgpt-")):
        return ChatOpenAI(
            openai_api_key=OPENAI_API_KEY,
            model_name=model_name,
            max_tokens=16384,
            temperature=0.7,
            streaming=True,
        )
    elif model_name.startswith("claude-"):
        return ChatAnthropic(
            anthropic_api_key=ANTHROPIC_API_KEY,
            model_name=model_name,
            max_tokens_to_sample=16384,
            temperature=0.7,
            streaming=True,
        )
    elif model_name.startswith("command-"):
        return ChatCohere(
            cohere_api_key=COHERE_API_KEY,
            model_name=model_name,
            max_tokens=16384,
            temperature=0.7,
            streaming=True,
        )
    elif model_name.startswith("gemini-"):
        return ChatGoogleGenerativeAI(
            google_api_key=GOOGLE_API_KEY,
            model=model_name,
            temperature=0.7,
            convert_system_message_to_human=True,
            streaming=True,
        )
    else:
        # Default to OpenAI if model is unknown or not specified
        return ChatOpenAI(
            openai_api_key=OPENAI_API_KEY,
            model_name="gpt-4o",
            max_tokens=16384,
            temperature=0.7,
            streaming=True,
        )

@main_app.post("/chat")
async def chat_endpoint(req: ChatRequest, user: dict = Depends(get_current_user)):
    user_id = user['user_id']
    llm = get_llm(req.model)
    
    # The history is now sent from the client
    history_messages = [message.dict() for message in req.history]

    # If web search is enabled, prepend search results to the last user message
    if req.search_web and history_messages and history_messages[-1]['role'] == 'user':
        user_query = history_messages[-1]['content']
        try:
            with DDGS() as ddgs:
                search_results = [r for r in ddgs.text(user_query, max_results=5)]
            
            if search_results:
                context = "\\n\\n".join([f"Title: {res['title']}\\nBody: {res['body']}" for res in search_results])
                web_prompt = (
                    "The user has requested a web search. Here are the top results. "
                    "Use this information to answer the user's query.\\n\\n"
                    "--- BEGIN WEB SEARCH RESULTS ---\\n"
                    f"{context}\\n"
                    "--- END WEB SEARCH RESULTS ---\\n\\n"
                    f"Original Query: {user_query}"
                )
                # Replace last user message with the one containing search results
                history_messages[-1]['content'] = web_prompt

        except Exception as e:
            print(f"Web search failed: {e}")

    # Convert our special 'context' messages into 'user' messages for the LLM
    llm_history = []
    for msg in history_messages:
        if msg.get('role') == 'context':
            llm_history.append({'role': 'user', 'content': msg.get('content', '')})
        else:
            llm_history.append(msg)
            
    async def bot_stream() -> AsyncGenerator[bytes, None]:
        response_accum = ""
        is_cancelled = False
        try:
            # The LLM astream method expects a list of messages
            async for chunk in llm.astream(llm_history): # Use the transformed history
                token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                response_accum += token
                yield token.encode('utf-8')
        except asyncio.CancelledError:
            is_cancelled = True
            print("Stream cancelled by client.")
        finally:
            if not is_cancelled and response_accum:
                # Save the full conversation history (including the AI's response)
                final_history = history_messages + [{"role": "assistant", "content": response_accum}]
                save_conversation(user_id, final_history)

    return StreamingResponse(bot_stream(), media_type="text/plain")

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
        documents = []
        for doc in docs:
            data = doc.to_dict()
            uploaded_at = data.get("uploadedAt")
            if uploaded_at and hasattr(uploaded_at, 'isoformat'):
                data['uploadedAt'] = uploaded_at.isoformat()
            documents.append(data)
        return JSONResponse(content=documents)
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

# File upload endpoint
@main_app.post("/upload")
async def upload_file(user: dict = Depends(get_current_user), file: UploadFile = File(...)):
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
                text = "\\n".join(text_pages)
        except Exception as e:
            # If extraction fails, we still proceed, but the context will be empty.
            print(f"Failed to extract text from {file.filename}: {e}")

        # Save metadata to Firestore
        doc_ref = db.collection("users").document(user_id).collection("documents").document(file.filename)
        doc_data = {
            "storagePath": file_path,
            "filename": file.filename,
            "contentType": file.content_type,
            "size": len(file_content),
            "uploadedAt": firestore.SERVER_TIMESTAMP,
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
        
        return JSONResponse(content={"message": f"Document '{filename}' deleted successfully."})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {e}")

main_app.mount("/", StaticFiles(directory="static", html=True), name="static")

@main_app.get("/")
def root():
    return FileResponse('static/index.html')

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
