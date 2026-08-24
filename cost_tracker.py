"""
Cost tracking module for RomaLume.
Estimates token counts and provider costs for operational reporting.
"""

try:
    import tiktoken
except ImportError:  # Keep pricing helpers usable in lightweight maintenance jobs.
    tiktoken = None

# Pricing per 1 MILLION tokens (verified August 24, 2026).
# Optional ``request`` is a flat provider fee per request.
MODEL_PRICING = {
    # Current OpenAI GPT-5.6 family
    "gpt-5.6-sol": {"input": 4.00, "output": 20.00},
    "gpt-5.6-terra": {"input": 2.00, "output": 12.00},
    "gpt-5.6-luna": {"input": 0.20, "output": 1.20},
    "gpt-5.6": {"input": 4.00, "output": 20.00},

    # Supported OpenAI models retained for background jobs and historical logs
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-5.5": {"input": 5.00, "output": 30.00},
    "gpt-5-nano": {"input": 0.05, "output": 0.40},
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
    "gpt-5.2": {"input": 1.75, "output": 14.00},
    "gpt-5.2-pro": {"input": 21.00, "output": 168.00},
    "gpt-5.2-codex": {"input": 1.75, "output": 14.00},

    # Current Anthropic Claude family
    "claude-fable-5": {"input": 10.00, "output": 50.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},

    # Historical Claude models
    "claude-opus-4-7": {"input": 5.00, "output": 25.00},
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
    "claude-opus-4-5": {"input": 5.00, "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},

    # Current Google Gemini family
    "gemini-3.7-flash": {"input": 0.75, "output": 3.75},
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    "gemini-3.1-pro": {"input": 2.00, "output": 12.00},

    # Historical Gemini models
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-3-pro": {"input": 2.00, "output": 12.00},
    "gemini-3-flash": {"input": 0.50, "output": 3.00},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},

    # Perplexity. Sonar Pro's default low-context search fee is $6/1K requests.
    "sonar-pro": {"input": 3.00, "output": 15.00, "request": 0.006},
}

# Full model catalog with metadata for the Models page
# This is the single source of truth for all available models
MODELS_CATALOG = [
    # OpenAI GPT-5.6
    {
        "id": "gpt-5.6-sol",
        "name": "GPT-5.6 Sol",
        "provider": "OpenAI",
        "category": "GPT-5.6",
        "description": "Frontier model for complex professional work and demanding coding",
        "input_price": 4.00,
        "output_price": 20.00,
        "context_window": 1050000,
        "best_for": ["Complex reasoning", "Professional work", "Coding"],
        "badge": "Latest",
    },
    {
        "id": "gpt-5.6-terra",
        "name": "GPT-5.6 Terra",
        "provider": "OpenAI",
        "category": "GPT-5.6",
        "description": "Balanced intelligence, latency, and cost for everyday professional work",
        "input_price": 2.00,
        "output_price": 12.00,
        "context_window": 1050000,
        "best_for": ["General chat", "Analysis", "Coding"],
    },
    {
        "id": "gpt-5.6-luna",
        "name": "GPT-5.6 Luna",
        "provider": "OpenAI",
        "category": "GPT-5.6",
        "description": "Fast, cost-sensitive GPT-5.6 model for high-volume workloads",
        "input_price": 0.20,
        "output_price": 1.20,
        "context_window": 1050000,
        "best_for": ["Quick answers", "Summarization", "High volume"],
    },
    # Anthropic Claude
    {
        "id": "claude-fable-5",
        "name": "Claude Fable 5",
        "provider": "Anthropic",
        "category": "Claude",
        "description": "Anthropic's most capable widely released model",
        "input_price": 10.00,
        "output_price": 50.00,
        "context_window": 1000000,
        "best_for": ["Deep reasoning", "Complex agents", "Critical work"],
        "badge": "Latest",
    },
    {
        "id": "claude-opus-5",
        "name": "Claude Opus 5",
        "provider": "Anthropic",
        "category": "Claude",
        "description": "High-capability model for complex agentic and enterprise work",
        "input_price": 5.00,
        "output_price": 25.00,
        "context_window": 1000000,
        "best_for": ["Agents", "Complex coding", "Deep reasoning"],
    },
    {
        "id": "claude-sonnet-5",
        "name": "Claude Sonnet 5",
        "provider": "Anthropic",
        "category": "Claude",
        "description": "Anthropic's best balance of speed and intelligence",
        "input_price": 2.00,
        "output_price": 10.00,
        "context_window": 1000000,
        "best_for": ["Writing", "Analysis", "Coding"],
    },
    {
        "id": "claude-haiku-4-5-20251001",
        "name": "Claude Haiku 4.5",
        "provider": "Anthropic",
        "category": "Claude",
        "description": "Fastest model with near-frontier intelligence",
        "input_price": 1.00,
        "output_price": 5.00,
        "context_window": 200000,
        "best_for": ["Fast responses", "High volume", "Cost-effective"],
    },
    # Google Gemini
    {
        "id": "gemini-3.7-flash",
        "name": "Gemini 3.7 Flash",
        "provider": "Google",
        "category": "Gemini",
        "description": "Google's latest GA workhorse for coding, agents, and multimodal reasoning",
        "input_price": 0.75,
        "output_price": 3.75,
        "context_window": 1000000,
        "best_for": ["Coding", "Agentic workflows", "Multimodal reasoning"],
        "badge": "Latest",
    },
    {
        "id": "gemini-3.5-flash-lite",
        "name": "Gemini 3.5 Flash-Lite",
        "provider": "Google",
        "category": "Gemini",
        "description": "Google's most cost-efficient GA model for high-volume tasks",
        "input_price": 0.30,
        "output_price": 2.50,
        "context_window": 1000000,
        "best_for": ["Fast tasks", "High volume", "Cost-effective"],
    },
    {
        "id": "gemini-3.1-pro-preview",
        "name": "Gemini 3.1 Pro",
        "provider": "Google",
        "category": "Gemini",
        "description": "Premium preview for advanced multimodal, coding, and agentic work",
        "input_price": 2.00,
        "output_price": 12.00,
        "context_window": 1000000,
        "best_for": ["Complex reasoning", "Agentic workflows", "Coding"],
        "badge": "Preview",
    },
    # Perplexity
    {
        "id": "sonar-pro",
        "name": "Sonar Pro",
        "provider": "Perplexity",
        "category": "Perplexity",
        "description": "Real-time web search with AI synthesis",
        "input_price": 3.00,
        "output_price": 15.00,
        "context_window": 200000,
        "best_for": ["Current events", "Research", "Fact-checking"],
        "badge": "Web Search",
    },
]

def get_models_catalog():
    """Return the full models catalog for the frontend."""
    return MODELS_CATALOG

# Default encoding for token estimation
DEFAULT_ENCODING = "cl100k_base"  # Works for most modern models


def get_encoding_for_model(model: str):
    """Get the appropriate tiktoken encoding for a model."""
    if tiktoken is None:
        return None
    try:
        # Try to get model-specific encoding
        if model.startswith("gpt-"):
            return tiktoken.encoding_for_model("gpt-4o")
        elif model.startswith("claude-"):
            # Claude uses similar tokenization to GPT-4
            return tiktoken.get_encoding(DEFAULT_ENCODING)
        elif model.startswith("gemini-"):
            # Gemini tokenization is different but cl100k is a reasonable approximation
            return tiktoken.get_encoding(DEFAULT_ENCODING)
        else:
            return tiktoken.get_encoding(DEFAULT_ENCODING)
    except Exception:
        return tiktoken.get_encoding(DEFAULT_ENCODING)


def estimate_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Estimate token count for a given text.

    Args:
        text: The text to tokenize
        model: Model name to use for tokenization rules

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    try:
        encoding = get_encoding_for_model(model)
        if encoding is None:
            return max(1, len(text) // 4)
        return len(encoding.encode(text))
    except Exception:
        # Fallback: rough estimate of ~4 chars per token
        return len(text) // 4


def estimate_conversation_tokens(messages: list, model: str = "gpt-4o") -> int:
    """
    Estimate total tokens for a conversation history.

    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model name for tokenization

    Returns:
        Estimated total token count
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content, model)
        # Add overhead for message formatting (~4 tokens per message)
        total += 4
    return total


def get_model_pricing(model: str) -> dict:
    """
    Get pricing for a model, with fallback for unknown models.

    Args:
        model: Model identifier

    Returns:
        Dict with 'input' and 'output' prices per 1M tokens
    """
    # Check for exact match
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]

    # Check for prefix match (e.g., "gpt-5-nano-2025-08-07" matches "gpt-5-nano")
    for prefix, pricing in MODEL_PRICING.items():
        if model.startswith(prefix):
            return pricing

    # Default fallback: use mid-tier pricing to avoid undercharging
    return {"input": 1.00, "output": 5.00}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate the estimated cost in USD for a request.

    Args:
        model: Model identifier
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens

    Returns:
        Cost in USD (as float, e.g., 0.0015 for $0.0015)
    """
    pricing = get_model_pricing(model)

    # Convert from per-million pricing to an estimated request cost.
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost + pricing.get("request", 0.0)


def calculate_cost_cents(model: str, input_tokens: int, output_tokens: int) -> int:
    """
    Calculate the estimated cost in cents (for database storage).

    Args:
        model: Model identifier
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens

    Returns:
        Cost in cents (integer, rounded up to avoid undercharging)
    """
    cost_usd = calculate_cost(model, input_tokens, output_tokens)
    # Round up to nearest cent, minimum 1 cent if there's any usage
    cents = int(cost_usd * 100 + 0.99) if cost_usd > 0 else 0
    return max(cents, 1) if (input_tokens > 0 or output_tokens > 0) else 0


def estimate_request_cost(
    model: str,
    input_text: str,
    output_text: str
) -> dict:
    """
    Estimate the full cost of a request.

    Args:
        model: Model identifier
        input_text: The input/prompt text (including conversation history)
        output_text: The generated output text

    Returns:
        Dict with token counts and costs
    """
    input_tokens = estimate_tokens(input_text, model)
    output_tokens = estimate_tokens(output_text, model)
    cost_usd = calculate_cost(model, input_tokens, output_tokens)

    return {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": round(cost_usd, 6),
        "cost_cents": calculate_cost_cents(model, input_tokens, output_tokens),
    }


def format_cost_display(cost_cents: int) -> str:
    """Format cost in cents for user display."""
    if cost_cents < 100:
        return f"${cost_cents}¢" if cost_cents > 0 else "$0"
    else:
        dollars = cost_cents / 100
        return f"${dollars:.2f}"
