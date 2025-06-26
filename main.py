import os
import pickle
from datetime import datetime
from typing import AsyncGenerator
from uuid import uuid4
import asyncio

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer
from langchain.memory import ConversationBufferMemory
from langchain_anthropic import ChatAnthropic
from langchain_cohere import ChatCohere
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from pypdf import PdfReader
import io
from duckduckgo_search import DDGS

load_dotenv()

# Secret key for signing session cookies
# In a production app, use a more secure key and load it from a secure location
SECRET_KEY = os.getenv("SECRET_KEY", "your-default-secret-key")
serializer = URLSafeTimedSerializer(SECRET_KEY)

main_app = FastAPI()

# Allow CORS for frontend
main_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    model: str
    search_web: bool = False

class ArchiveRequest(BaseModel):
    model: str
    archive_name: str | None = None
    project_name: str | None = "General"

class ClearMemoryRequest(BaseModel):
    pass

class LoadArchiveRequest(BaseModel):
    filename: str
    project_name: str

# Directory to store conversation memory files
MEMORY_DIR = os.path.join(os.path.dirname(__file__), "conversation_memory")
ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), "archives")

def get_session_id(request: Request, response: Response) -> str:
    """Gets or creates a session ID."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = str(uuid4())
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            samesite="lax",
            secure=False,  # Set to True in production with HTTPS
        )
    return session_id

def get_memory_filepath(session_id: str) -> str:
    """Returns the full path for a session's memory file."""
    return os.path.join(MEMORY_DIR, f"{session_id}.pkl")

def load_memory(session_id: str) -> ConversationBufferMemory:
    """Loads a ConversationBufferMemory object from a file."""
    filepath = get_memory_filepath(session_id)
    if os.path.exists(filepath):
        try:
            with open(filepath, "rb") as f:
                return pickle.load(f)
        except (pickle.UnpicklingError, EOFError):
            # Handle cases where the file is corrupted or empty
            return ConversationBufferMemory(return_messages=True)
    return ConversationBufferMemory(return_messages=True)

def save_memory(session_id: str, memory: ConversationBufferMemory):
    """Saves a ConversationBufferMemory object to a file."""
    filepath = get_memory_filepath(session_id)
    with open(filepath, "wb") as f:
        pickle.dump(memory, f)

def delete_memory(session_id: str):
    """Deletes a session's memory file."""
    filepath = get_memory_filepath(session_id)
    if os.path.exists(filepath):
        os.remove(filepath)

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
            max_tokens=16384, # Increased token limit
            temperature=0.7,
            streaming=True,
        )
    elif model_name.startswith("claude-"):
        return ChatAnthropic(
            anthropic_api_key=ANTHROPIC_API_KEY,
            model_name=model_name,
            max_tokens_to_sample=16384, # Increased token limit
            temperature=0.7,
            streaming=True,
        )
    elif model_name.startswith("command-"):
        return ChatCohere(
            cohere_api_key=COHERE_API_KEY,
            model_name=model_name,
            max_tokens=16384, # Increased token limit
            temperature=0.7,
            streaming=True,
        )
    elif model_name.startswith("gemini-"):
        return ChatGoogleGenerativeAI(
            google_api_key=GOOGLE_API_KEY,
            model=model_name,
            temperature=0.7,
            convert_system_message_to_human=True, # Gemini needs this
            streaming=True,
        )
    else:
        # Default to OpenAI if model is unknown or not specified
        return ChatOpenAI(
            openai_api_key=OPENAI_API_KEY,
            model_name="gpt-4o",
            max_tokens=16384, # Increased token limit
            temperature=0.7,
            streaming=True,
        )

@main_app.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request, response: Response):
    session_id = get_session_id(request, response)
    memory = load_memory(session_id)
    llm = get_llm(req.model)

    user_message = req.message
    if req.search_web:
        try:
            with DDGS() as ddgs:
                search_results = [r for r in ddgs.text(user_message, max_results=5)]
            
            if search_results:
                context = "\n\n".join([f"Title: {res['title']}\nBody: {res['body']}" for res in search_results])
                web_prompt = (
                    "The user has requested a web search. Here are the top results. "
                    "Use this information to answer the user's query.\n\n"
                    "--- BEGIN WEB SEARCH RESULTS ---\n"
                    f"{context}\n"
                    "--- END WEB SEARCH RESULTS ---\n"
                )
                memory.chat_memory.add_user_message(web_prompt)

        except Exception as e:
            print(f"Web search failed: {e}")

    # Add user message to memory
    memory.chat_memory.add_user_message(user_message)

    async def bot_stream() -> AsyncGenerator[bytes, None]:
        response_accum = ""
        is_cancelled = False
        try:
            # Pass the list of messages directly to the LLM
            async for chunk in llm.astream(memory.chat_memory.messages):
                token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                response_accum += token
                yield token.encode('utf-8')
        except asyncio.CancelledError:
            is_cancelled = True
            print("Stream cancelled by client.")
        finally:
            # Only save the full response if the stream was not cancelled
            if not is_cancelled and response_accum:
                memory.chat_memory.add_ai_message(response_accum)
                save_memory(session_id, memory)

    return StreamingResponse(bot_stream(), media_type="text/plain", headers=response.headers)

@main_app.post("/archive")
async def archive_chat(req: ArchiveRequest, request: Request, response: Response):
    session_id = get_session_id(request, response)
    memory = load_memory(session_id)

    if not memory.chat_memory.messages:
        return JSONResponse(status_code=404, content={"error": "No chat session found to archive."})
    
    project_name = req.project_name or "General"
    project_dir = os.path.join(ARCHIVE_DIR, project_name)
    os.makedirs(project_dir, exist_ok=True)

    if req.archive_name:
        # Sanitize the filename
        sanitized_name = "".join(c for c in req.archive_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        filename = f"{sanitized_name}.md"
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"chat_archive_{timestamp}.md"

    filepath = os.path.join(project_dir, filename)
    
    archive_header = f"# Chat Archive - {filename}\n\n**Model:** `{req.model}`\n**Project:** `{project_name}`\n\n---\n\n"
    archive_content = archive_header
    for msg in memory.chat_memory.messages:
        if msg.type == 'human':
            if msg.content.startswith("[File uploaded:"):
                archive_content += f"**System:**\n```\n{msg.content}\n```\n\n---\n\n"
            else:
                archive_content += f"**User:**\n{msg.content}\n\n---\n\n"
        elif msg.type == 'ai':
            archive_content += f"**Assistant:**\n{msg.content}\n\n---\n\n"
            
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(archive_content)
        
    return JSONResponse(content={"message": f"Chat archived to {filename}"})

@main_app.post("/clear_memory")
async def clear_memory_endpoint(request: Request, response: Response):
    """Clears the conversation history for a given session."""
    session_id = get_session_id(request, response)
    delete_memory(session_id)
    return JSONResponse(status_code=200, content={"message": "Conversation history cleared."})


# File upload endpoint
@main_app.post("/upload")
async def upload_file(request: Request, response: Response, file: UploadFile = File(...), model: str = Form(None)):
    session_id = get_session_id(request, response)
    
    allowed_extensions = ('.md', '.txt', '.pdf')
    if not file.filename.endswith(allowed_extensions):
        return JSONResponse(status_code=400, content={"error": f"Only {', '.join(allowed_extensions)} files are allowed."})

    content = ""
    try:
        file_bytes = await file.read()
        if file.filename.endswith('.pdf'):
            pdf_stream = io.BytesIO(file_bytes)
            reader = PdfReader(pdf_stream)
            for page in reader.pages:
                content += page.extract_text() or ""
        else:
            content = file_bytes.decode('utf-8', errors='ignore')

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to process file: {e}"})
        
    memory = load_memory(session_id)
    # Add file content to memory as a user message with a clearer instruction
    file_prompt = (
        f"The user has uploaded a file named '{file.filename}'. Its content is provided below for context. "
        "Use this content to answer any subsequent questions from the user.\n\n"
        "--- BEGIN FILE CONTENT ---\n"
        f"{content}\n"
        "--- END FILE CONTENT ---"
    )
    memory.chat_memory.add_user_message(file_prompt)
    save_memory(session_id, memory)
    return JSONResponse(content={"message": f"File '{file.filename}' uploaded and its content is now in the conversation context."})

@main_app.get("/archives")
async def get_archives():
    """Returns a list of saved chat archives, organized by project."""
    if not os.path.exists(ARCHIVE_DIR):
        return JSONResponse(content={})
    
    projects = {}
    for project_name in os.listdir(ARCHIVE_DIR):
        project_dir = os.path.join(ARCHIVE_DIR, project_name)
        if os.path.isdir(project_dir):
            archives = [
                f for f in os.listdir(project_dir) 
                if f.endswith('.md') and os.path.isfile(os.path.join(project_dir, f))
            ]
            if archives:
                projects[project_name] = sorted(archives, reverse=True)

    response = JSONResponse(content=projects)
    # Add cache-busting headers for Chrome compatibility
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@main_app.post("/load_archive")
async def load_archive(req: LoadArchiveRequest, request: Request, response: Response):
    """Loads a chat archive into the current session memory."""
    session_id = get_session_id(request, response)
    filename = req.filename
    project_name = req.project_name
    
    filepath = os.path.join(ARCHIVE_DIR, project_name, filename)

    if not os.path.exists(filepath):
        return JSONResponse(status_code=404, content={"error": "Archive not found."})

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Reconstruct memory from archive
    memory = ConversationBufferMemory(return_messages=True)
    # Simple parsing logic, assuming the format used in archive_chat
    messages = content.split('\n\n---\n\n')
    for msg_block in messages:
        if msg_block.startswith('**User:**'):
            memory.chat_memory.add_user_message(msg_block.replace('**User:**\n', ''))
        elif msg_block.startswith('**Assistant:**'):
            memory.chat_memory.add_ai_message(msg_block.replace('**Assistant:**\n', ''))
        elif msg_block.startswith('**System:**'):
            memory.chat_memory.add_user_message(msg_block.replace('**System:**\n```\n', '').replace('\n```', ''))

    save_memory(session_id, memory)
    return JSONResponse(content={"message": "Archive loaded successfully."})

@main_app.get("/history")
async def get_history(request: Request, response: Response):
    """Gets the conversation history for a given session."""
    session_id = get_session_id(request, response)
    memory = load_memory(session_id)
    history = [
        {"type": msg.type, "content": msg.content}
        for msg in memory.chat_memory.messages
    ]
    return JSONResponse(content={"history": history})


@main_app.get("/")
def root():
    return FileResponse('static/index.html')


# Mount static files
main_app.mount("/static", StaticFiles(directory="static"), name="static")
