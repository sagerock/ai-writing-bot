import os
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, List, Optional
import asyncio
from uuid import uuid4
import io
import sys
import json
import socket

os.environ["GRPC_DNS_RESOLVER"] = "native"  # Force gRPC to use system DNS

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Depends, Header, UploadFile, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from pypdf import PdfReader
import csv
import base64
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
import google.generativeai as genai
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI
from google.cloud.firestore_v1.query import Query
from google.cloud.firestore_v1.transaction import Transaction
from google.cloud.firestore_v1.document import DocumentReference
from cost_tracker import estimate_tokens, estimate_request_cost, calculate_cost_cents, get_models_catalog

# Stripe integration (optional - gracefully handle if not configured)
try:
    import stripe
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    STRIPE_ENABLED = bool(stripe.api_key)
    if STRIPE_ENABLED:
        print("✓ Stripe initialized")
    else:
        print("⚠ Stripe not configured (STRIPE_SECRET_KEY not set)")
except ImportError:
    STRIPE_ENABLED = False
    print("⚠ Stripe not installed")

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
# Support both environment variable (for Render/Railway) and local file (for local dev)
firebase_creds = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
if firebase_creds:
    # Use environment variable (Render/Railway deployment)
    try:
        # Try parsing as-is first
        cred_dict = json.loads(firebase_creds)
        cred = credentials.Certificate(cred_dict)
        print("✓ Using Firebase credentials from environment variable")
    except json.JSONDecodeError as e:
        # Railway may escape quotes or add extra escaping - try to fix common issues
        try:
            # Remove potential outer quotes and unescape
            cleaned = firebase_creds.strip()
            if cleaned.startswith('"') and cleaned.endswith('"'):
                cleaned = cleaned[1:-1]
            # Replace escaped quotes
            cleaned = cleaned.replace('\\"', '"')
            # Replace escaped newlines with actual newlines
            cleaned = cleaned.replace('\\n', '\n')
            cred_dict = json.loads(cleaned)
            cred = credentials.Certificate(cred_dict)
            print("✓ Using Firebase credentials from environment variable (after cleanup)")
        except json.JSONDecodeError as e2:
            print(f"✗ Error parsing FIREBASE_SERVICE_ACCOUNT_JSON: {e}")
            print(f"✗ Cleanup attempt also failed: {e2}")
            print(f"✗ First 100 chars of value: {firebase_creds[:100]}")
            raise e
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

# mem0 removed - replaced with user profile system
# Profiles are stored in Firestore at users/{user_id}/settings/profile
print("✓ User profile system enabled (mem0 removed)")

# Email Marketing Tool integration (for onboarding sequences)
EMAIL_MARKETING_API_URL = os.getenv("EMAIL_MARKETING_API_URL", "https://api.mail.sagerock.com")
EMAIL_MARKETING_API_KEY = os.getenv("EMAIL_MARKETING_API_KEY")
EMAIL_MARKETING_CLIENT_ID = os.getenv("EMAIL_MARKETING_CLIENT_ID")
if EMAIL_MARKETING_API_KEY and EMAIL_MARKETING_CLIENT_ID:
    print("✓ Email marketing integration configured")
else:
    print("⚠ Email marketing not configured (EMAIL_MARKETING_API_KEY or EMAIL_MARKETING_CLIENT_ID not set)")

main_app = FastAPI()



def send_to_email_marketing_background(email: str, tags: List[str] = None):
    """
    Send a new user to the email marketing tool for onboarding sequences.
    This runs in a background task to not block the signup flow.
    """
    import requests

    if not EMAIL_MARKETING_API_KEY or not EMAIL_MARKETING_CLIENT_ID:
        print("Email marketing not configured, skipping")
        return

    if tags is None:
        tags = ["romalume-signup"]

    try:
        response = requests.post(
            f"{EMAIL_MARKETING_API_URL}/api/contacts/upsert",
            headers={
                "Authorization": f"Bearer {EMAIL_MARKETING_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "client_id": EMAIL_MARKETING_CLIENT_ID,
                "email": email.lower().strip(),
                "tags": tags
            },
            timeout=10
        )

        if response.ok:
            result = response.json()
            print(f"✓ Sent {email} to email marketing ({result.get('action', 'unknown')})")
        else:
            print(f"✗ Email marketing API error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Failed to send to email marketing: {e}")


def log_usage_with_cost(
    user_id: str,
    model: str,
    original_model: str,
    routed_category: str,
    input_text: str,
    output_text: str,
    search_web: bool = False,
    search_docs: bool = False
):
    """
    Log usage with actual token counts and cost calculation.
    Also updates monthly aggregates for billing.
    """
    try:
        # Calculate tokens and cost
        input_tokens = estimate_tokens(input_text, model)
        output_tokens = estimate_tokens(output_text, model)
        cost_cents = calculate_cost_cents(model, input_tokens, output_tokens)

        now = datetime.now()
        month_key = now.strftime("%Y-%m")
        date_key = now.strftime("%Y-%m-%d")

        # Log individual request
        db.collection("usage_logs").add({
            "user_id": user_id,
            "model": model,
            "original_model": original_model,
            "routed_category": routed_category,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "date_key": date_key,
            "month_key": month_key,
            "search_web": search_web,
            "search_docs": search_docs,
            # New cost tracking fields
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_cents": cost_cents,
        })

        # Update monthly aggregate for this user
        monthly_ref = db.collection("user_monthly_usage").document(f"{user_id}_{month_key}")
        monthly_ref.set({
            "user_id": user_id,
            "month": month_key,
            "total_ai_cost_cents": firestore.Increment(cost_cents),
            "total_requests": firestore.Increment(1),
            "total_input_tokens": firestore.Increment(input_tokens),
            "total_output_tokens": firestore.Increment(output_tokens),
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

        # Update user's all-time totals
        db.collection("users").document(user_id).set({
            "all_time_ai_cost_cents": firestore.Increment(cost_cents),
            "all_time_requests": firestore.Increment(1),
        }, merge=True)

        print(f"Usage logged: {model}, {input_tokens}+{output_tokens} tokens, ${cost_cents/100:.4f}")

    except Exception as e:
        print(f"Failed to log usage with cost: {e}")


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

# --- Public Endpoints (no auth required) ---

@main_app.get("/models")
async def get_models():
    """
    Get the catalog of available AI models with pricing.
    This is a public endpoint - no authentication required.
    """
    return {
        "models": get_models_catalog(),
        "pricing_note": "Prices shown are per 1 million tokens. Actual costs depend on usage.",
        "auto_routing_info": "When using 'Auto' mode, we intelligently route your request to the most appropriate model based on the task type."
    }

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
    charity_updates: bool = True

class EmailRequest(BaseModel):
    subject: str
    content: str
    email_type: str  # "feature_updates", "bug_fixes", "pricing_changes", "usage_tips", "charity_updates", "all"
    preview: bool = False

class UserChatSettings(BaseModel):
    simplified_mode: bool = True
    default_model: str = "auto"
    default_temperature: float = 0.7
    always_ask_mode: bool = False

class FeedbackRequest(BaseModel):
    message_id: str  # Unique identifier for the message (generated on frontend)
    rating: str  # "up" or "down"
    model: str  # The model that generated the response
    routed_category: str | None = None  # If auto-routed, what category
    message_snippet: str | None = None  # First 200 chars of the message for context

# --- Signup Rate Limiting ---
# Limit new account creation to prevent abuse (3 accounts per IP per day)
SIGNUP_RATE_LIMIT = 3
SIGNUP_RATE_WINDOW_HOURS = 24
SIGNUP_RATE_LIMIT_WHITELIST = ["108.194.182.188"]  # IPs exempt from rate limiting

def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header (set by proxies/load balancers)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs; first one is the client
        return forwarded_for.split(",")[0].strip()
    # Check X-Real-IP header (common with nginx)
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"

@main_app.get("/signup/check-rate-limit")
async def check_signup_rate_limit(request: Request):
    """Check if this IP can create a new account."""
    client_ip = get_client_ip(request)

    # Skip rate limiting for whitelisted IPs
    if client_ip in SIGNUP_RATE_LIMIT_WHITELIST:
        return {"allowed": True, "attempts_remaining": 999}

    # Get signup attempts from this IP in the last 24 hours
    signup_ref = db.collection("signup_rate_limits").document(client_ip)
    signup_doc = signup_ref.get()

    if signup_doc.exists:
        data = signup_doc.to_dict()
        attempts = data.get("attempts", [])

        # Filter to only attempts within the rate window
        cutoff = datetime.now(timezone.utc) - timedelta(hours=SIGNUP_RATE_WINDOW_HOURS)
        recent_attempts = [a for a in attempts if a > cutoff]

        if len(recent_attempts) >= SIGNUP_RATE_LIMIT:
            # Calculate when they can try again
            oldest_attempt = min(recent_attempts)
            can_retry_at = oldest_attempt + timedelta(hours=SIGNUP_RATE_WINDOW_HOURS)
            hours_remaining = (can_retry_at - datetime.now(timezone.utc)).total_seconds() / 3600

            return {
                "allowed": False,
                "reason": f"Too many accounts created from this network. Please try again in {int(hours_remaining) + 1} hours.",
                "attempts_remaining": 0
            }

        return {
            "allowed": True,
            "attempts_remaining": SIGNUP_RATE_LIMIT - len(recent_attempts)
        }

    return {
        "allowed": True,
        "attempts_remaining": SIGNUP_RATE_LIMIT
    }

class SignupRequest(BaseModel):
    email: str = None  # Optional - for email marketing integration

@main_app.post("/signup/record")
async def record_signup(request: Request, background_tasks: BackgroundTasks, body: SignupRequest = None):
    """Record a successful signup attempt for rate limiting and send to email marketing."""
    client_ip = get_client_ip(request)

    signup_ref = db.collection("signup_rate_limits").document(client_ip)
    signup_doc = signup_ref.get()

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=SIGNUP_RATE_WINDOW_HOURS)

    if signup_doc.exists:
        data = signup_doc.to_dict()
        attempts = data.get("attempts", [])
        # Keep only recent attempts + new one
        recent_attempts = [a for a in attempts if a > cutoff]
        recent_attempts.append(now)
        signup_ref.update({"attempts": recent_attempts, "last_attempt": now})
    else:
        signup_ref.set({"attempts": [now], "last_attempt": now})

    # Send to email marketing tool in the background
    if body and body.email:
        background_tasks.add_task(
            send_to_email_marketing_background,
            email=body.email,
            tags=["romalume-signup"]
        )

    return {"recorded": True}

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
    gpt5_models = ["gpt-5-mini", "gpt-5-nano", "gpt-5.2", "gpt-5.2-pro", "gpt-5.2-codex"]
    return any(model_name.startswith(model) for model in gpt5_models)

# Model routing configuration - optimized for cost efficiency
# Costs per ~2K tokens:
#   Gemini 2.0 Flash: $0.0005 (cheapest)
#   GPT-5 Mini: $0.002
#   Haiku 4.5: $0.006
#   Gemini 2.5 Flash: $0.003
#   Sonnet 4.5: $0.018
#   Opus 4.5: $0.03 (premium quality)
ROUTING_MODELS = {
    "simple": "gemini-2.0-flash",      # Quick facts - ultra cheap & fast
    "general": "gpt-5.2",              # Everyday tasks - good quality, 12% cheaper than Sonnet
    "coding": "gpt-5.2-codex",        # Complex coding - purpose-built, 47% cheaper than Opus
    "writing": "claude-sonnet-4-5",    # Creative writing - great quality, cost effective
    "analysis": "gemini-2.5-pro",      # Analysis, research - strong reasoning, 63% cheaper
    "science": "gemini-2.5-pro",       # Scientific analysis - good at explanations, cheaper
    "realtime": "sonar-pro",           # Current events, live data - needs web search
}

ROUTER_PROMPT = """Classify this message into ONE category. Return ONLY the category name.

Categories:
- simple: Greetings, thanks, yes/no questions, quick facts, definitions, translations, unit conversions, simple lookups, short direct answers, follow-up questions, clarifications
- general: Casual chat, opinions, advice, recommendations, everyday questions, summarizing, rephrasing, explaining concepts simply, brainstorming ideas, lists
- coding: Writing NEW code, debugging errors, implementing features, refactoring, complex technical problems, architecture decisions, code review
- writing: Creative writing (poems, stories, fiction), formal essays, persuasive copy, emotional/nuanced content, voice/tone sensitive writing
- analysis: Deep data analysis, research synthesis, compare/contrast with reasoning, strategic planning, business analysis, detailed evaluations
- science: Complex scientific explanations, mathematical proofs, physics problems, detailed educational content
- realtime: Current events, news, weather, stock prices, sports scores, "what happened today/recently", live data, anything requiring up-to-date information from the internet

ROUTING RULES (follow strictly):
1. Short messages (<20 words) asking factual questions -> simple
2. "What is X?" or "Define X" or "How do you say X in Y?" -> simple
3. Quick code QUESTIONS (not writing code) -> general
4. Explaining code that exists -> general
5. WRITING new code or fixing bugs -> coding
6. Creative, emotional, or voice-sensitive writing -> writing
7. Simple summaries or rewording -> general
8. Deep analysis requiring reasoning -> analysis
9. Questions about current/recent events, news, prices, weather, scores -> realtime
10. Questions containing "today", "latest", "current", "recent", "now", "this week" -> realtime

When uncertain between simple/general, choose simple.
When uncertain between general/analysis, choose general.

Message: "{message}"

Category:"""

async def route_to_best_model(user_message: str) -> tuple[str, str]:
    """
    Use Gemini 2.0 Flash to quickly classify the message and route to the best model.
    Returns (model_name, category) tuple.
    """
    try:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-2.0-flash")

        response = await model.generate_content_async(
            ROUTER_PROMPT.format(message=user_message[:500]),
            generation_config=genai.GenerationConfig(
                max_output_tokens=20,
                temperature=0.0  # Deterministic for consistent routing
            )
        )

        raw_response = response.text.strip().lower()
        print(f"Router raw response: '{raw_response}'")

        # Extract category from response - handle various formats
        # Could be "simple", "simple.", "Category: simple", etc.
        category = None
        for cat in ROUTING_MODELS.keys():
            if cat in raw_response:
                category = cat
                break

        if category:
            routed_model = ROUTING_MODELS[category]
            print(f"Router: '{category}' -> {routed_model}")
            return routed_model, category
        else:
            print(f"Router: Could not extract category from '{raw_response}', defaulting to general")
            return ROUTING_MODELS["general"], "general"

    except Exception as e:
        print(f"Router failed: {e}, defaulting to general")
        return ROUTING_MODELS["general"], "general"

async def generate_gpt5_response(
    req: ChatRequest,
    user_id: str,
    profile_context: str = "",
    original_model: str = None,
    routed_category: str = None
):
    """Generate streaming response for GPT-5 models using Chat Completions API with GPT-5 parameters."""
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Convert history to messages format (convert 'context' role to 'user' for API compatibility)
    messages = []
    for msg in req.history:
        role = msg.role
        if role == 'context':
            role = 'user'  # API only accepts: system, assistant, user, function, tool, developer
        messages.append({
            "role": role,
            "content": msg.content
        })

    # Add base system prompt with optional profile context
    base_instruction = "When the user changes topics or asks about something new, respond to that topic directly without forcing connections to previous unrelated topics in this conversation. Treat each distinct subject independently unless there's a clear and explicit connection."

    if profile_context:
        system_content = f"{base_instruction}\n\nHere is what you know about this user:\n{profile_context}\n\nUse this context only when directly relevant to the current question."
    else:
        system_content = base_instruction

    messages.insert(0, {
        "role": "system",
        "content": system_content
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

        # Auto-save to mem0 - get the last user message
        last_user_msg = None
        for msg in reversed(req.history):
            if msg.role == 'user':
                last_user_msg = msg.content
                break
        if last_user_msg and full_response:
            save_to_mem0_background(user_id, last_user_msg, full_response)

        # Log usage with actual token counts and costs
        input_text = "\n".join([m.get('content', '') for m in messages])
        log_usage_with_cost(
            user_id=user_id,
            model=req.model,
            original_model=original_model or req.model,
            routed_category=routed_category,
            input_text=input_text,
            output_text=full_response,
            search_web=req.search_web,
            search_docs=req.search_docs,
        )

    except Exception as e:
        error_msg = f"Error in GPT-5 response: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        yield json.dumps(f"ERROR: {str(e)}")

async def generate_chat_response(req: ChatRequest, user_id: str):
    user_ref = db.collection("users").document(user_id)

    # Check subscription status and credits
    transaction = db.transaction()

    @firestore.transactional
    def check_access_and_update(transaction: Transaction, user_ref: DocumentReference):
        """
        Check if user can access the service:
        1. Active subscribers → unlimited access (no credit deduction)
        2. Free users → use credits (100 free messages)
        """
        user_snapshot = user_ref.get(transaction=transaction)

        if not user_snapshot.exists:
            # New user - give them 100 free messages
            initial_credits = 100
            transaction.set(user_ref, {
                "credits": initial_credits - 1,
                "credits_used": 1,
                "subscription_status": "none"
            })
            return {"is_subscriber": False, "credits_remaining": initial_credits - 1}

        user_data = user_snapshot.to_dict()
        subscription_status = user_data.get("subscription_status", "none")

        # Active subscribers get unlimited access
        if subscription_status == "active":
            return {"is_subscriber": True, "credits_remaining": None}

        # Free users use credits
        credits = user_data.get("credits", 0)

        if credits <= 0:
            raise HTTPException(
                status_code=402,
                detail="You've used all your free messages! Subscribe to continue and support Houseless Movement."
            )

        transaction.update(user_ref, {
            "credits": firestore.Increment(-1),
            "credits_used": firestore.Increment(1)
        })

        return {"is_subscriber": False, "credits_remaining": credits - 1}

    try:
        access_info = check_access_and_update(transaction, user_ref)
    except HTTPException as e:
        yield f"data: ERROR: {e.detail}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Send a heartbeat immediately so the browser knows the stream is alive
    yield ": ping\n\n"

    # --- Auto-routing: If model is "auto", use router to select best model ---
    routed_category = None
    original_model = req.model  # Store for logging
    if req.model == "auto":
        # Find the last user message for routing
        last_user_msg = None
        for msg in reversed(req.history):
            if msg.role == 'user':
                last_user_msg = msg.content
                break

        if last_user_msg:
            routed_model, routed_category = await route_to_best_model(last_user_msg)
            print(f"Auto-routing: '{last_user_msg[:50]}...' -> {routed_model} ({routed_category})")
            # Update the request model
            req = ChatRequest(
                history=req.history,
                model=routed_model,
                search_web=req.search_web,
                search_docs=req.search_docs,
                temperature=req.temperature
            )
            # Send routing info to frontend
            yield f"data: {json.dumps({'routed_model': routed_model, 'routed_category': routed_category})}\n\n"
        else:
            # No user message, default to general
            req = ChatRequest(
                history=req.history,
                model=ROUTING_MODELS["general"],
                search_web=req.search_web,
                search_docs=req.search_docs,
                temperature=req.temperature
            )

    # Usage logging moved to AFTER response generation (so we can capture output tokens)
    # Store variables needed for logging
    usage_log_data = {
        "user_id": user_id,
        "model": req.model,
        "original_model": original_model,
        "routed_category": routed_category,
        "search_web": req.search_web,
        "search_docs": req.search_docs,
    }

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
                    print(f"RAG searching for user {user_id}: '{last_user_msg[:100]}...'")
                    results = rag.search(user_id, last_user_msg, top_k=5, score_threshold=0.5)

                    if results:
                        context_parts = []
                        for r in results:
                            context_parts.append(f"[From: {r['filename']}]\n{r['chunk_text']}")
                        rag_context = "\n\n---\n\n".join(context_parts)
                        print(f"RAG found {len(results)} relevant chunks for user {user_id}")
        except Exception as e:
            print(f"RAG search failed (non-fatal): {e}")

    # --- Retrieve user profile for personalization ---
    profile_context = ""
    try:
        profile_ref = db.collection("users").document(user_id).collection("settings").document("profile")
        profile_doc = profile_ref.get()

        if profile_doc.exists:
            profile = profile_doc.to_dict()
            profile_parts = []
            currently_parts = []

            # Always Remember goes first - user-specified priority info
            if profile.get("always_remember"):
                profile_parts.append(f"IMPORTANT - User wants you to always remember: {profile['always_remember']}")

            # Format static profile into readable context
            if profile.get("work"):
                profile_parts.append(f"Work: {profile['work']}")
            if profile.get("background"):
                profile_parts.append(f"Background: {profile['background']}")
            if profile.get("location"):
                profile_parts.append(f"Location: {profile['location']}")
            if profile.get("family"):
                profile_parts.append(f"Family: {', '.join(profile['family'])}")
            if profile.get("pets"):
                profile_parts.append(f"Pets: {', '.join(profile['pets'])}")
            if profile.get("interests"):
                profile_parts.append(f"Interests: {', '.join(profile['interests'])}")
            if profile.get("philosophies"):
                profile_parts.append(f"Values/Philosophies: {', '.join(profile['philosophies'])}")
            if profile.get("communication_preferences"):
                profile_parts.append(f"Communication preferences: {', '.join(profile['communication_preferences'])}")
            if profile.get("projects"):
                profile_parts.append(f"Ongoing projects: {', '.join(profile['projects'])}")
            if profile.get("other"):
                profile_parts.append(f"Other: {', '.join(profile['other'])}")

            # Currently section - dynamic recent context
            if profile.get("currently"):
                currently_parts = profile['currently']

            if profile_parts or currently_parts:
                context_sections = []
                if profile_parts:
                    context_sections.append("About this user:\n" + "\n".join(f"- {p}" for p in profile_parts))
                if currently_parts:
                    context_sections.append("Currently:\n" + "\n".join(f"- {c}" for c in currently_parts))
                profile_context = "\n\n".join(context_sections)
                print(f"Loaded user profile for {user_id} ({len(profile_parts)} static fields, {len(currently_parts)} currently items)")
    except Exception as e:
        print(f"Profile retrieval failed (non-fatal): {e}")

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
        async for token in generate_gpt5_response(
            req, user_id, profile_context,
            original_model=usage_log_data["original_model"],
            routed_category=usage_log_data["routed_category"]
        ):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"
        return

    llm = get_llm(req.model, req.temperature)
    history_messages = [message.dict() for message in req.history]

    # Add base system prompt with optional profile context for non-GPT5 models
    base_instruction = "When the user changes topics or asks about something new, respond to that topic directly without forcing connections to previous unrelated topics in this conversation. Treat each distinct subject independently unless there's a clear and explicit connection."

    if profile_context:
        system_content = f"{base_instruction}\n\nHere is what you know about this user:\n{profile_context}\n\nUse this context only when directly relevant to the current question."
    else:
        system_content = base_instruction

    history_messages.insert(0, {
        "role": "system",
        "content": system_content
    })

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

        # Log usage with actual token counts and costs
        input_text = "\n".join([m.get('content', '') for m in llm_history])
        log_usage_with_cost(
            user_id=usage_log_data["user_id"],
            model=usage_log_data["model"],
            original_model=usage_log_data["original_model"],
            routed_category=usage_log_data["routed_category"],
            input_text=input_text,
            output_text=response_accum,
            search_web=usage_log_data["search_web"],
            search_docs=usage_log_data["search_docs"],
        )

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

# Legacy mem0 endpoints - deprecated in favor of user profile system
# Kept for backward compatibility but return deprecation notices

@main_app.post("/save_memory")
async def save_memory(req: ChatRequest, user: dict = Depends(get_current_user)):
    """Deprecated: Use /user/profile/generate instead."""
    return JSONResponse(content={"message": "Memory system replaced with user profiles. Use /user/profile/generate to build your profile."})

@main_app.get("/user/memories")
async def get_user_memories(user: dict = Depends(get_current_user)):
    """Deprecated: Use /user/profile instead."""
    return JSONResponse(content={"memories": [], "message": "Memory system replaced with user profiles. Use GET /user/profile instead."})

@main_app.delete("/user/memories/{memory_id}")
async def delete_user_memory(memory_id: str, user: dict = Depends(get_current_user)):
    """Deprecated: Memories replaced with user profile system."""
    return JSONResponse(content={"message": "Memory system has been replaced with user profiles."})

@main_app.delete("/user/memories")
async def delete_all_user_memories(user: dict = Depends(get_current_user)):
    """Deprecated: Memories replaced with user profile system."""
    return JSONResponse(content={"message": "Memory system has been replaced with user profiles."})

# --- User Profile System ---
# Replaces mem0 with a thoughtful, curated user profile built from conversation archives

class UserProfile(BaseModel):
    """Structured user profile built from conversation history."""
    always_remember: Optional[str] = ""  # User-defined permanent notes (max 500 chars)
    currently: Optional[List[str]] = []  # Dynamic recent context (updated frequently)
    family: Optional[List[str]] = []
    pets: Optional[List[str]] = []
    work: Optional[str] = ""
    background: Optional[str] = ""
    location: Optional[str] = ""
    interests: Optional[List[str]] = []
    philosophies: Optional[List[str]] = []
    communication_preferences: Optional[List[str]] = []
    projects: Optional[List[str]] = []
    other: Optional[List[str]] = []
    last_updated: Optional[str] = None
    last_archive_count: Optional[int] = 0  # Track archive count at last generation

@main_app.get("/user/profile")
async def get_user_profile(user: dict = Depends(get_current_user)):
    """Get the user's curated profile."""
    user_id = user['user_id']
    try:
        profile_ref = db.collection("users").document(user_id).collection("settings").document("profile")
        profile_doc = profile_ref.get()

        if profile_doc.exists:
            return JSONResponse(content={"profile": profile_doc.to_dict()})
        else:
            # Return empty profile structure
            return JSONResponse(content={"profile": {
                "always_remember": "",
                "currently": [],
                "family": [],
                "pets": [],
                "work": "",
                "background": "",
                "location": "",
                "interests": [],
                "philosophies": [],
                "communication_preferences": [],
                "projects": [],
                "other": [],
                "last_updated": None,
                "last_archive_count": 0
            }})
    except Exception as e:
        print(f"Error fetching profile: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@main_app.put("/user/profile")
async def update_user_profile(profile: UserProfile, user: dict = Depends(get_current_user)):
    """Manually update the user's profile."""
    user_id = user['user_id']
    try:
        profile_ref = db.collection("users").document(user_id).collection("settings").document("profile")
        profile_data = profile.model_dump()
        profile_data["last_updated"] = datetime.now().isoformat()
        profile_ref.set(profile_data)
        return JSONResponse(content={"message": "Profile updated successfully", "profile": profile_data})
    except Exception as e:
        print(f"Error updating profile: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@main_app.post("/user/profile/generate")
async def generate_user_profile(user: dict = Depends(get_current_user)):
    """Analyze conversation archives and generate a curated user profile.

    - Static fields (work, family, etc.) are only filled if currently empty
    - 'currently' field is always updated from recent conversations
    - 'always_remember' is never touched
    """
    user_id = user['user_id']

    try:
        # Get existing profile to preserve fields
        profile_ref = db.collection("users").document(user_id).collection("settings").document("profile")
        existing_profile_doc = profile_ref.get()
        existing_profile = existing_profile_doc.to_dict() if existing_profile_doc.exists else {}

        # Fetch archives
        archives_ref = db.collection("users").document(user_id).collection("archives")
        archives_list = list(archives_ref.order_by("archivedAt", direction=firestore.Query.DESCENDING).limit(50).stream())
        total_archive_count = len(list(archives_ref.stream()))

        # Split into recent (for "currently") and all (for static profile)
        recent_archives = archives_list[:5]  # Last 5 for "currently"

        # Extract conversation content
        def extract_conversations(archive_list, max_convs=30):
            conversations = []
            for archive in archive_list:
                data = archive.to_dict()
                messages = data.get("messages", [])
                if messages:
                    conv_text = []
                    for msg in messages:
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role in ["user", "assistant"] and content:
                            conv_text.append(f"{role}: {content[:500]}")
                    if conv_text:
                        conversations.append("\n".join(conv_text[:10]))
            return conversations[:max_convs]

        all_conversations = extract_conversations(archives_list)
        recent_conversations = extract_conversations(recent_archives, max_convs=5)

        if not all_conversations:
            return JSONResponse(content={
                "message": "No conversation history found to analyze",
                "profile": None
            })

        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Check which static fields need filling
        static_fields = ['family', 'pets', 'work', 'background', 'location',
                         'interests', 'philosophies', 'communication_preferences', 'projects', 'other']
        empty_fields = []
        for field in static_fields:
            val = existing_profile.get(field)
            if not val or (isinstance(val, list) and len(val) == 0) or (isinstance(val, str) and val.strip() == ""):
                empty_fields.append(field)

        profile_data = dict(existing_profile)  # Start with existing data

        # Only generate static fields if there are empty ones
        if empty_fields:
            combined_text = "\n\n---\n\n".join(all_conversations)
            if len(combined_text) > 50000:
                combined_text = combined_text[:50000]

            profile_prompt = f"""Analyze these conversations and extract profile information for the user.
Focus on meaningful personal details, not random conversational fragments.
Extract ONLY information that is clearly stated or strongly implied. Leave fields empty if uncertain.

I ONLY need these fields (leave others out):
{chr(10).join(f'- {field}' for field in empty_fields)}

Field descriptions:
- family: array of family members (e.g., ["wife Sarah", "son Jake"])
- pets: array of pets (e.g., ["dog Max"])
- work: string describing their job/profession
- background: string with relevant background
- location: string with location if mentioned
- interests: array of hobbies/interests
- philosophies: array of values/beliefs
- communication_preferences: array of communication style preferences
- projects: array of ongoing projects
- other: array of other meaningful facts

Return ONLY valid JSON with just the requested fields, no other text."""

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": profile_prompt},
                    {"role": "user", "content": f"Conversations:\n\n{combined_text}"}
                ],
                temperature=0.3,
                max_tokens=2000
            )

            profile_text = response.choices[0].message.content.strip()
            if profile_text.startswith("```"):
                profile_text = profile_text.split("```")[1]
                if profile_text.startswith("json"):
                    profile_text = profile_text[4:]
            profile_text = profile_text.strip()

            try:
                new_fields = json.loads(profile_text)
                # Only update empty fields
                for field in empty_fields:
                    if field in new_fields and new_fields[field]:
                        profile_data[field] = new_fields[field]
            except json.JSONDecodeError as e:
                print(f"Failed to parse static profile JSON: {e}")

        # Always update "currently" from recent conversations
        if recent_conversations:
            recent_text = "\n\n---\n\n".join(recent_conversations)

            currently_prompt = """Based on these recent conversations, extract what the user is CURRENTLY focused on.
This should capture their recent context - what they're working on right now, recent topics, current focus areas.

Return a JSON object with one field:
- currently: array of 3-5 short phrases about their current focus (e.g., ["Building user profile system", "Exploring AI memory approaches", "Working on RomaLume project"])

Focus on recent/current activities, not permanent traits. Return ONLY valid JSON."""

            currently_response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": currently_prompt},
                    {"role": "user", "content": f"Recent conversations:\n\n{recent_text}"}
                ],
                temperature=0.3,
                max_tokens=500
            )

            currently_text = currently_response.choices[0].message.content.strip()
            if currently_text.startswith("```"):
                currently_text = currently_text.split("```")[1]
                if currently_text.startswith("json"):
                    currently_text = currently_text[4:]
            currently_text = currently_text.strip()

            try:
                currently_data = json.loads(currently_text)
                profile_data["currently"] = currently_data.get("currently", [])
            except json.JSONDecodeError as e:
                print(f"Failed to parse currently JSON: {e}")

        # Preserve always_remember and update metadata
        profile_data["always_remember"] = existing_profile.get("always_remember", "")
        profile_data["last_updated"] = datetime.now().isoformat()
        profile_data["last_archive_count"] = total_archive_count

        profile_ref.set(profile_data)

        return JSONResponse(content={
            "message": "Profile generated successfully",
            "profile": profile_data
        })

    except Exception as e:
        print(f"Error generating profile: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@main_app.post("/user/profile/auto-generate")
async def auto_generate_profile(user: dict = Depends(get_current_user)):
    """Check if profile needs auto-generation and generate if needed.

    Auto-generates if:
    - No profile exists and user has 5+ archives
    - Profile exists but 10+ new archives since last generation (updates 'currently')
    """
    user_id = user['user_id']

    try:
        # Get current profile
        profile_ref = db.collection("users").document(user_id).collection("settings").document("profile")
        profile_doc = profile_ref.get()

        # Count total archives
        archives_ref = db.collection("users").document(user_id).collection("archives")
        total_archives = len(list(archives_ref.stream()))

        if profile_doc.exists:
            profile = profile_doc.to_dict()
            last_archive_count = profile.get("last_archive_count", 0)

            # Only regenerate if 10+ new archives since last generation
            if total_archives - last_archive_count < 10:
                return JSONResponse(content={
                    "action": "skipped",
                    "reason": f"Only {total_archives - last_archive_count} new archives since last generation",
                    "profile": profile
                })
        else:
            # No profile - only generate if user has 5+ archives
            if total_archives < 5:
                return JSONResponse(content={
                    "action": "skipped",
                    "reason": f"Only {total_archives} archives, need 5+ to generate profile",
                    "profile": None
                })

        # Trigger profile generation using the main generate function
        result = await generate_user_profile(user)
        result_data = json.loads(result.body.decode())

        if "error" in result_data:
            return JSONResponse(content={
                "action": "failed",
                "reason": result_data.get("error", "Unknown error"),
                "profile": None
            })

        return JSONResponse(content={
            "action": "generated",
            "reason": "Profile auto-generated successfully",
            "profile": result_data.get("profile")
        })

    except Exception as e:
        print(f"Error in auto-generate profile: {e}")
        return JSONResponse(content={
            "action": "failed",
            "reason": str(e),
            "profile": None
        })

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

        # Get title and preview from stored data or generate from messages
        title = data.get("title")
        preview = data.get("preview")
        messages = data.get("messages", [])

        # If no title stored, use first user message as title
        if not title and messages:
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    # Show full query up to 200 chars
                    title = content[:200]
                    if len(content) > 200:
                        title += "..."
                    break

        # If no preview stored, use first assistant response (truncated)
        if not preview and messages:
            for msg in messages:
                if msg.get("role") == "assistant":
                    preview = msg.get("content", "")[:150]
                    if len(msg.get("content", "")) > 150:
                        preview += "..."
                    break

        project_archives[project].append({
            "id": archive.id,
            "model": data.get("model"),
            "archivedAt": archived_at,
            "title": title or archive.id.replace(".md", ""),
            "preview": preview or "No preview available",
            "messageCount": len(messages)
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


# --- Billing & Subscription Endpoints ---

@main_app.get("/user/billing")
async def get_user_billing(user: dict = Depends(get_current_user)):
    """Get user's billing dashboard data including AI costs and charity contribution."""
    user_id = user['user_id']

    try:
        # Get user data
        user_ref = db.collection("users").document(user_id)
        user_snapshot = user_ref.get()
        user_data = user_snapshot.to_dict() if user_snapshot.exists else {}

        # Get current month's usage
        now = datetime.now()
        month_key = now.strftime("%Y-%m")
        monthly_ref = db.collection("user_monthly_usage").document(f"{user_id}_{month_key}")
        monthly_snapshot = monthly_ref.get()
        monthly_data = monthly_snapshot.to_dict() if monthly_snapshot.exists else {}

        # Get subscription info
        subscription_amount_cents = user_data.get("subscription_amount", 2000)  # Default $20
        subscription_status = user_data.get("subscription_status", "none")

        # Calculate current month's AI cost
        current_month_ai_cost_cents = monthly_data.get("total_ai_cost_cents", 0)
        current_month_requests = monthly_data.get("total_requests", 0)

        # Calculate charity contribution (subscription - AI costs, minimum 0)
        current_month_charity_cents = max(0, subscription_amount_cents - current_month_ai_cost_cents)

        # Get all-time totals
        all_time_ai_cost_cents = user_data.get("all_time_ai_cost_cents", 0)
        all_time_requests = user_data.get("all_time_requests", 0)

        # Calculate all-time charity (would need to track subscription payments)
        # For now, estimate based on months subscribed
        all_time_charity_cents = user_data.get("all_time_charity_cents", 0)

        # Check if user is approaching their subscription limit (80% threshold)
        usage_warning = current_month_ai_cost_cents >= (subscription_amount_cents * 0.8)

        # Get free messages remaining for non-subscribers
        free_messages_remaining = user_data.get("credits", 100) if subscription_status != "active" else None
        free_messages_used = user_data.get("credits_used", 0)

        return JSONResponse(content={
            "subscription": {
                "status": subscription_status,
                "amount_cents": subscription_amount_cents,
                "amount_display": f"${subscription_amount_cents / 100:.2f}",
            },
            "free_tier": {
                "messages_remaining": free_messages_remaining,
                "messages_used": free_messages_used,
                "total_free": 100,
            },
            "current_month": {
                "month": month_key,
                "ai_cost_cents": current_month_ai_cost_cents,
                "ai_cost_display": f"${current_month_ai_cost_cents / 100:.2f}",
                "charity_cents": current_month_charity_cents,
                "charity_display": f"${current_month_charity_cents / 100:.2f}",
                "requests": current_month_requests,
                "usage_percent": round((current_month_ai_cost_cents / subscription_amount_cents) * 100, 1) if subscription_amount_cents > 0 else 0,
            },
            "all_time": {
                "ai_cost_cents": all_time_ai_cost_cents,
                "ai_cost_display": f"${all_time_ai_cost_cents / 100:.2f}",
                "charity_cents": all_time_charity_cents,
                "charity_display": f"${all_time_charity_cents / 100:.2f}",
                "requests": all_time_requests,
            },
            "usage_warning": usage_warning,
        })

    except Exception as e:
        print(f"Error getting billing data: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to get billing data"}
        )


@main_app.get("/user/subscription")
async def get_user_subscription(user: dict = Depends(get_current_user)):
    """Get user's subscription status."""
    user_id = user['user_id']

    try:
        user_ref = db.collection("users").document(user_id)
        user_snapshot = user_ref.get()

        if not user_snapshot.exists:
            return JSONResponse(content={
                "status": "none",
                "amount_cents": 0,
                "stripe_customer_id": None,
            })

        user_data = user_snapshot.to_dict()

        # Convert Firestore timestamp to ISO string if present
        current_period_end = user_data.get("subscription_current_period_end")
        if current_period_end:
            current_period_end = current_period_end.isoformat() if hasattr(current_period_end, 'isoformat') else str(current_period_end)

        return JSONResponse(content={
            "status": user_data.get("subscription_status", "none"),
            "amount_cents": user_data.get("subscription_amount", 0),
            "stripe_customer_id": user_data.get("stripe_customer_id"),
            "current_period_end": current_period_end,
        })

    except Exception as e:
        print(f"Error getting subscription: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to get subscription data"}
        )


# --- Stripe Payment Endpoints ---

class CreateCheckoutRequest(BaseModel):
    amount_cents: int = 2000  # Default $20, minimum
    success_url: str
    cancel_url: str


@main_app.post("/stripe/create-checkout")
async def create_stripe_checkout(
    req: CreateCheckoutRequest,
    user: dict = Depends(get_current_user)
):
    """Create a Stripe checkout session for subscription."""
    if not STRIPE_ENABLED:
        return JSONResponse(
            status_code=503,
            content={"error": "Payments not configured"}
        )

    user_id = user['user_id']
    user_email = user.get('email', '')

    try:
        # Ensure minimum $20
        amount_cents = max(req.amount_cents, 2000)

        # Check if user already has a Stripe customer ID
        user_ref = db.collection("users").document(user_id)
        user_snapshot = user_ref.get()
        user_data = user_snapshot.to_dict() if user_snapshot.exists else {}
        stripe_customer_id = user_data.get("stripe_customer_id")

        # Create or retrieve Stripe customer
        if not stripe_customer_id:
            customer = stripe.Customer.create(
                email=user_email,
                metadata={"firebase_user_id": user_id}
            )
            stripe_customer_id = customer.id
            # Save customer ID
            user_ref.set({"stripe_customer_id": stripe_customer_id}, merge=True)

        # Create checkout session with variable pricing
        # Using a price_data approach for flexible amounts
        session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "RomaLume Subscription",
                        "description": f"Monthly subscription - 100% of profits go to Houseless Movement charity",
                    },
                    "unit_amount": amount_cents,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            mode="subscription",
            success_url=req.success_url,
            cancel_url=req.cancel_url,
            metadata={
                "firebase_user_id": user_id,
                "amount_cents": str(amount_cents),
            },
        )

        return JSONResponse(content={
            "checkout_url": session.url,
            "session_id": session.id,
        })

    except Exception as e:
        print(f"Stripe checkout error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to create checkout: {str(e)}"}
        )


@main_app.post("/stripe/create-portal")
async def create_stripe_portal(user: dict = Depends(get_current_user)):
    """Create a Stripe customer portal session for managing subscription."""
    if not STRIPE_ENABLED:
        return JSONResponse(
            status_code=503,
            content={"error": "Payments not configured"}
        )

    user_id = user['user_id']

    try:
        user_ref = db.collection("users").document(user_id)
        user_snapshot = user_ref.get()

        if not user_snapshot.exists:
            return JSONResponse(
                status_code=404,
                content={"error": "User not found"}
            )

        user_data = user_snapshot.to_dict()
        stripe_customer_id = user_data.get("stripe_customer_id")

        if not stripe_customer_id:
            return JSONResponse(
                status_code=400,
                content={"error": "No subscription found"}
            )

        # Create portal session
        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=os.getenv("FRONTEND_URL", "https://ai-writing-tool-bdebc.web.app") + "/account",
        )

        return JSONResponse(content={"portal_url": session.url})

    except Exception as e:
        print(f"Stripe portal error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to create portal: {str(e)}"}
        )


class UpdateSubscriptionRequest(BaseModel):
    amount_cents: int


@main_app.post("/stripe/update-subscription")
async def update_stripe_subscription(req: UpdateSubscriptionRequest, user: dict = Depends(get_current_user)):
    """Update subscription amount (upgrade/downgrade)."""
    if not STRIPE_ENABLED:
        return JSONResponse(
            status_code=503,
            content={"error": "Payments not configured"}
        )

    if req.amount_cents < 2000 or req.amount_cents > 10000:
        return JSONResponse(
            status_code=400,
            content={"error": "Amount must be between $20 and $100"}
        )

    user_id = user['user_id']

    try:
        user_ref = db.collection("users").document(user_id)
        user_snapshot = user_ref.get()

        if not user_snapshot.exists:
            return JSONResponse(
                status_code=404,
                content={"error": "User not found"}
            )

        user_data = user_snapshot.to_dict()
        subscription_id = user_data.get("stripe_subscription_id")

        if not subscription_id:
            return JSONResponse(
                status_code=400,
                content={"error": "No active subscription found"}
            )

        # Retrieve current subscription
        subscription = stripe.Subscription.retrieve(subscription_id)

        if subscription.status != "active":
            return JSONResponse(
                status_code=400,
                content={"error": "Subscription is not active"}
            )

        # Get the current subscription item ID and product ID
        subscription_item_id = subscription["items"]["data"][0]["id"]
        current_price = subscription["items"]["data"][0]["price"]
        product_id = current_price["product"]

        # Check if product is active, reactivate or create new if needed
        try:
            product = stripe.Product.retrieve(product_id)
            if not product.active:
                # Reactivate the product
                stripe.Product.modify(product_id, active=True)
        except stripe.error.StripeError:
            # If we can't retrieve/modify, create a new product
            product = stripe.Product.create(
                name="RomaLume Subscription",
                description="Monthly subscription - 100% of profits go to Houseless Movement charity",
            )
            product_id = product.id

        # Create a new price for the product
        new_price = stripe.Price.create(
            product=product_id,
            unit_amount=req.amount_cents,
            currency="usd",
            recurring={"interval": "month"},
        )

        # Update the subscription with the new price
        updated_subscription = stripe.Subscription.modify(
            subscription_id,
            items=[{
                "id": subscription_item_id,
                "price": new_price.id,
            }],
            proration_behavior="create_prorations",  # Charge/credit the difference immediately
        )

        # Update Firestore with new amount
        user_ref.update({
            "subscription_amount": req.amount_cents,
        })

        return JSONResponse(content={
            "success": True,
            "new_amount_cents": req.amount_cents,
            "message": f"Subscription updated to ${req.amount_cents / 100:.0f}/month"
        })

    except stripe.error.StripeError as e:
        print(f"Stripe update error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to update subscription: {str(e)}"}
        )
    except Exception as e:
        print(f"Subscription update error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to update subscription"}
        )


@main_app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    if not STRIPE_ENABLED:
        return JSONResponse(status_code=503, content={"error": "Payments not configured"})

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        print(f"Invalid payload: {e}")
        return JSONResponse(status_code=400, content={"error": "Invalid payload"})
    except stripe.error.SignatureVerificationError as e:
        print(f"Invalid signature: {e}")
        return JSONResponse(status_code=400, content={"error": "Invalid signature"})

    # Handle subscription events
    event_type = event["type"]
    data = event["data"]["object"]

    print(f"Stripe webhook: {event_type}")

    try:
        if event_type == "checkout.session.completed":
            # New subscription created
            customer_id = data.get("customer")
            subscription_id = data.get("subscription")
            metadata = data.get("metadata", {})
            user_id = metadata.get("firebase_user_id")
            amount_cents = int(metadata.get("amount_cents", 2000))

            if user_id:
                # Get subscription details
                subscription = stripe.Subscription.retrieve(subscription_id)

                db.collection("users").document(user_id).set({
                    "stripe_customer_id": customer_id,
                    "stripe_subscription_id": subscription_id,
                    "subscription_status": "active",
                    "subscription_amount": amount_cents,
                    "subscription_started_at": firestore.SERVER_TIMESTAMP,
                    "subscription_current_period_end": datetime.fromtimestamp(subscription.current_period_end),
                }, merge=True)

                print(f"Subscription activated for user {user_id}: ${amount_cents/100}")

        elif event_type == "customer.subscription.updated":
            subscription_id = data.get("id")
            status = data.get("status")
            customer_id = data.get("customer")

            # Find user by customer ID
            users = db.collection("users").where("stripe_customer_id", "==", customer_id).limit(1).get()

            for user_doc in users:
                user_doc.reference.update({
                    "subscription_status": status,
                    "subscription_current_period_end": datetime.fromtimestamp(data.get("current_period_end", 0)),
                })
                print(f"Subscription updated for {user_doc.id}: {status}")

        elif event_type == "customer.subscription.deleted":
            customer_id = data.get("customer")

            # Find user by customer ID
            users = db.collection("users").where("stripe_customer_id", "==", customer_id).limit(1).get()

            for user_doc in users:
                user_doc.reference.update({
                    "subscription_status": "canceled",
                })
                print(f"Subscription canceled for {user_doc.id}")

        elif event_type == "invoice.paid":
            customer_id = data.get("customer")
            amount_paid = data.get("amount_paid", 0)

            # Find user and update charity tracking
            users = db.collection("users").where("stripe_customer_id", "==", customer_id).limit(1).get()

            for user_doc in users:
                # Get current month's AI cost to calculate charity portion
                user_id = user_doc.id
                month_key = datetime.now().strftime("%Y-%m")
                monthly_ref = db.collection("user_monthly_usage").document(f"{user_id}_{month_key}")
                monthly_snapshot = monthly_ref.get()
                monthly_data = monthly_snapshot.to_dict() if monthly_snapshot.exists else {}
                ai_cost = monthly_data.get("total_ai_cost_cents", 0)

                charity_amount = max(0, amount_paid - ai_cost)

                user_doc.reference.set({
                    "all_time_charity_cents": firestore.Increment(charity_amount),
                    "last_payment_at": firestore.SERVER_TIMESTAMP,
                }, merge=True)

                print(f"Invoice paid for {user_id}: ${amount_paid/100}, charity: ${charity_amount/100}")

    except Exception as e:
        print(f"Webhook processing error: {e}")
        # Still return 200 to acknowledge receipt
        import traceback
        traceback.print_exc()

    return JSONResponse(content={"status": "ok"})


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
    # Text-based files
    text_extensions = ('.md', '.txt', '.pdf', '.csv', '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.sh', '.bash', '.sql', '.java', '.c', '.cpp', '.h', '.go', '.rs', '.rb', '.php')
    # Image files (will be base64 encoded for vision models)
    image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
    # Word documents
    docx_extensions = ('.docx',)

    allowed_extensions = text_extensions + image_extensions + docx_extensions

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    filename_lower = file.filename.lower()
    if not any(filename_lower.endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail=f"File type not supported. Allowed: {', '.join(allowed_extensions)}")

    try:
        file_content = await file.read()

        # Extract text based on file type
        text = ""
        is_image = False

        if filename_lower.endswith(text_extensions):
            if filename_lower.endswith('.pdf'):
                reader = PdfReader(io.BytesIO(file_content))
                text_pages = [page.extract_text() or "" for page in reader.pages]
                text = "\n".join(text_pages)
            elif filename_lower.endswith('.csv'):
                # Parse CSV and format as readable text
                csv_text = file_content.decode('utf-8')
                reader = csv.reader(io.StringIO(csv_text))
                rows = list(reader)
                if rows:
                    # Format as markdown table for better readability
                    header = rows[0]
                    text = "| " + " | ".join(header) + " |\n"
                    text += "| " + " | ".join(["---"] * len(header)) + " |\n"
                    for row in rows[1:]:
                        text += "| " + " | ".join(row) + " |\n"
            else:
                # Plain text or code files
                text = file_content.decode('utf-8')
        elif filename_lower.endswith(image_extensions):
            # For images, encode as base64 for vision model
            is_image = True
            ext = filename_lower.split('.')[-1]
            mime_type = f"image/{ext}" if ext != 'jpg' else "image/jpeg"
            b64 = base64.b64encode(file_content).decode('utf-8')
            text = f"[Image: {file.filename}]\ndata:{mime_type};base64,{b64}"
        elif filename_lower.endswith('.docx'):
            # Try to extract text from docx
            try:
                from docx import Document
                doc = Document(io.BytesIO(file_content))
                text = "\n".join([para.text for para in doc.paragraphs])
            except ImportError:
                text = "[Word document uploaded - python-docx not installed for text extraction]"
            except Exception as e:
                text = f"[Could not extract text from Word document: {e}]"

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


@main_app.get("/document/{filename}/download")
async def download_document(filename: str, user: dict = Depends(get_current_user)):
    """Generate a signed URL to download the original file."""
    user_id = user['user_id']

    try:
        # Verify document exists in Firestore
        doc_ref = db.collection("users").document(user_id).collection("documents").document(filename)
        doc_snapshot = doc_ref.get()
        if not doc_snapshot.exists:
            raise HTTPException(status_code=404, detail="Document not found.")

        doc_data = doc_snapshot.to_dict()
        storage_path = doc_data.get("storagePath", f"{user_id}/documents/{filename}")

        # Get blob and generate signed URL
        blob = bucket.blob(storage_path)
        if not blob.exists():
            raise HTTPException(status_code=404, detail="File not found in storage.")

        # Generate signed URL valid for 1 hour
        from datetime import timedelta
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="GET",
            response_disposition=f'attachment; filename="{filename}"'
        )

        return JSONResponse(content={"download_url": url, "filename": filename})

    except HTTPException:
        raise
    except Exception as e:
        print(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate download link: {e}")


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

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    credits: Optional[int] = None
    is_admin: Optional[bool] = None

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

@main_app.put("/admin/users/{user_id}")
async def update_user(user_id: str, user_update: UserUpdate, _: dict = Depends(get_current_admin_user)):
    """Update user fields (display_name, credits, is_admin)."""
    try:
        # Update display name in Firebase Auth
        if user_update.display_name is not None:
            firebase_auth.update_user(user_id, display_name=user_update.display_name)

        # Update credits in Firestore
        if user_update.credits is not None:
            user_ref = db.collection("users").document(user_id)
            user_ref.set({"credits": user_update.credits}, merge=True)

        # Update admin status in Firebase Auth custom claims
        if user_update.is_admin is not None:
            firebase_auth.set_custom_user_claims(user_id, {"admin": user_update.is_admin})

        return {"message": "User updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@main_app.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, _: dict = Depends(get_current_admin_user)):
    """Permanently delete a user and all their data."""
    try:
        # Delete from Firestore - user document and subcollections
        user_ref = db.collection("users").document(user_id)

        # Delete subcollections (archives, conversations, documents)
        for subcollection_name in ['archives', 'conversations', 'documents']:
            try:
                subcollection = user_ref.collection(subcollection_name)
                docs = list(subcollection.stream())
                for doc in docs:
                    doc.reference.delete()
            except Exception as sub_err:
                print(f"Error deleting {subcollection_name} for {user_id}: {sub_err}")

        # Delete the user document itself
        user_ref.delete()

        # Delete from Firebase Auth (this must be last as it invalidates the user)
        firebase_auth.delete_user(user_id)

        print(f"User {user_id} deleted successfully")
        return {"message": f"User {user_id} deleted successfully"}
    except Exception as e:
        print(f"Error deleting user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@main_app.post("/admin/users/{user_id}/unsubscribe")
async def unsubscribe_user(user_id: str, _: dict = Depends(get_current_admin_user)):
    """Unsubscribe a user from all system emails."""
    try:
        user_ref = db.collection("users").document(user_id)

        # Set all email preferences to False
        user_ref.set({
            "email_preferences": {
                "feature_updates": False,
                "bug_fixes": False,
                "pricing_changes": False,
                "usage_tips": False,
                "charity_updates": False
            }
        }, merge=True)

        print(f"User {user_id} unsubscribed from all emails")
        return {"message": "User unsubscribed from all emails"}
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
# Formula: (input_price * 1K + output_price * 1K) / 1M = cost per 2K tokens
MODEL_COSTS = {
    # OpenAI GPT-5 family
    "gpt-5-nano": 0.0005,       # $0.05 input / $0.40 output
    "gpt-5-mini": 0.002,        # $0.25 input / $2.00 output
    "gpt-5.2-codex": 0.016,     # $1.75 input / $14.00 output (coding-optimized)
    "gpt-5.2-pro": 0.19,        # $21.00 input / $168.00 output (premium)
    "gpt-5.2": 0.016,           # $1.75 input / $14.00 output (flagship)
    # Anthropic Claude
    "claude-opus-4-6": 0.03,   # $5 input / $25 output (flagship)
    "claude-opus-4-5": 0.03,   # $5 input / $25 output (legacy)
    "claude-sonnet": 0.018,    # $3 input / $15 output
    "claude-haiku": 0.006,     # $1 input / $5 output
    # Google Gemini
    "gemini-3-pro": 0.014,  # $2 input / $12 output - best multimodal
    "gemini-2.5-pro": 0.011,# $1.25 input / $10 output - coding/reasoning
    "gemini-2.5-flash": 0.003, # $0.30 input / $2.50 output - hybrid reasoning
    "gemini-2.0-flash": 0.0005, # $0.10 input / $0.40 output - balanced
    # Perplexity
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
        "charity_updates": "#e91e63",
        "all": "#6c757d",
        "test": "#9b59b6"
    }
    return colors.get(email_type, "#6c757d")

def get_type_label(email_type: str) -> str:
    """Get label for email type badge."""
    labels = {
        "feature_updates": "🚀 New Feature",
        "bug_fixes": "🐛 Bug Fix",
        "pricing_changes": "💰 Pricing Update",
        "usage_tips": "💡 Usage Tip",
        "charity_updates": "❤️ Charity Update",
        "all": "📢 Announcement",
        "test": "🧪 Test Email"
    }
    return labels.get(email_type, "📢 Announcement")

async def get_users_for_email(email_type: str) -> List[dict]:
    """Get users who should receive emails of this type."""

    # Test email type - only send to admin email
    if email_type == "test":
        return [{
            "uid": "test",
            "email": "sage@sagerock.com",
            "display_name": "Test Admin"
        }]

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
            "usage_tips": True,
            "charity_updates": True
        })
        return email_prefs
    else:
        # Return default preferences for new users
        return {
            "feature_updates": True,
            "bug_fixes": True,
            "pricing_changes": True,
            "usage_tips": True,
            "charity_updates": True
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
            "usage_tips": preferences.usage_tips,
            "charity_updates": preferences.charity_updates
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
        "default_model": "auto",
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

@main_app.post("/feedback")
async def submit_feedback(
    feedback: FeedbackRequest,
    user: dict = Depends(get_current_user)
):
    """Submit thumbs up/down feedback for an AI response."""
    user_id = user["user_id"]

    try:
        db.collection("feedback").add({
            "user_id": user_id,
            "message_id": feedback.message_id,
            "rating": feedback.rating,
            "model": feedback.model,
            "routed_category": feedback.routed_category,
            "message_snippet": feedback.message_snippet,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "date_key": datetime.now().strftime("%Y-%m-%d")
        })
        return {"message": "Feedback recorded successfully"}
    except Exception as e:
        print(f"Failed to record feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record feedback: {str(e)}")

@main_app.get("/admin/analytics/feedback")
async def get_feedback_analytics(
    days: int = 30,
    _: dict = Depends(get_current_admin_user)
):
    """Get feedback analytics - thumbs up/down by model."""
    try:
        feedback_logs = db.collection("feedback")

        if days == 0:
            logs = list(feedback_logs.stream())
        else:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            logs = list(feedback_logs.where("date_key", ">=", start_date).stream())

        # Aggregate by model and rating
        model_feedback = {}
        category_feedback = {}
        total_up = 0
        total_down = 0

        for log in logs:
            data = log.to_dict()
            model = data.get("model", "unknown")
            rating = data.get("rating", "unknown")
            category = data.get("routed_category", "direct")

            # Model aggregation
            if model not in model_feedback:
                model_feedback[model] = {"up": 0, "down": 0, "total": 0}
            model_feedback[model][rating] = model_feedback[model].get(rating, 0) + 1
            model_feedback[model]["total"] += 1

            # Category aggregation (for auto-routed)
            if category:
                if category not in category_feedback:
                    category_feedback[category] = {"up": 0, "down": 0, "total": 0}
                category_feedback[category][rating] = category_feedback[category].get(rating, 0) + 1
                category_feedback[category]["total"] += 1

            if rating == "up":
                total_up += 1
            elif rating == "down":
                total_down += 1

        # Calculate satisfaction rates
        for model, stats in model_feedback.items():
            if stats["total"] > 0:
                stats["satisfaction_rate"] = round(stats["up"] / stats["total"] * 100, 1)

        for category, stats in category_feedback.items():
            if stats["total"] > 0:
                stats["satisfaction_rate"] = round(stats["up"] / stats["total"] * 100, 1)

        total = total_up + total_down
        overall_satisfaction = round(total_up / total * 100, 1) if total > 0 else 0

        return {
            "total_feedback": total,
            "total_positive": total_up,
            "total_negative": total_down,
            "overall_satisfaction_rate": overall_satisfaction,
            "by_model": model_feedback,
            "by_category": category_feedback
        }
    except Exception as e:
        print(f"Feedback analytics error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get feedback analytics: {str(e)}")

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
                "usage_tips": True,
                "charity_updates": True
            })
        else:
            email_prefs = {
                "feature_updates": True,
                "bug_fixes": True,
                "pricing_changes": True,
                "usage_tips": True,
                "charity_updates": True
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
                    <div class="preference-item {'enabled' if email_prefs.get('charity_updates', True) else 'disabled'}">
                        ❤️ <strong>Houseless Movement Updates:</strong> {'Enabled' if email_prefs.get('charity_updates', True) else 'Disabled'}
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