"""
Cost tracking module for RomaLume.
Estimates token counts and calculates actual AI costs for transparent billing.
"""

import tiktoken
from typing import Optional

# Pricing per 1 MILLION tokens (as of February 2026)
# Format: {"input": price_per_1M_input, "output": price_per_1M_output}
MODEL_PRICING = {
    # OpenAI GPT-5 family
    "gpt-5-nano": {"input": 0.05, "output": 0.40},
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
    "gpt-5.2": {"input": 1.75, "output": 14.00},
    "gpt-5.2-pro": {"input": 21.00, "output": 168.00},
    "gpt-5.2-codex": {"input": 1.75, "output": 14.00},

    # Anthropic Claude
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
    "claude-opus-4-5": {"input": 5.00, "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},

    # Google Gemini
    "gemini-3.1-pro": {"input": 2.00, "output": 12.00},
    "gemini-3-pro": {"input": 2.00, "output": 12.00},
    "gemini-3-flash": {"input": 0.50, "output": 3.00},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},

    # Perplexity
    "sonar-pro": {"input": 3.00, "output": 15.00},
}

# Full model catalog with metadata for the Models page
# This is the single source of truth for all available models
MODELS_CATALOG = [
    # OpenAI GPT-5 Series
    {
        "id": "gpt-5-nano-2025-08-07",
        "name": "GPT-5 Nano",
        "provider": "OpenAI",
        "category": "GPT-5 Series",
        "description": "Ultra-fast, cost-effective model for simple tasks",
        "input_price": 0.05,
        "output_price": 0.40,
        "context_window": 128000,
        "best_for": ["Quick answers", "Simple tasks", "High volume"],
    },
    {
        "id": "gpt-5-mini-2025-08-07",
        "name": "GPT-5 Mini",
        "provider": "OpenAI",
        "category": "GPT-5 Series",
        "description": "Balanced performance and cost for everyday tasks",
        "input_price": 0.25,
        "output_price": 2.00,
        "context_window": 128000,
        "best_for": ["General chat", "Writing assistance", "Summarization"],
    },
    {
        "id": "gpt-5.2-2025-12-11",
        "name": "GPT-5.2",
        "provider": "OpenAI",
        "category": "GPT-5 Series",
        "description": "Flagship model for coding and agentic tasks with 400K context window",
        "input_price": 1.75,
        "output_price": 14.00,
        "context_window": 400000,
        "best_for": ["Coding tasks", "Agentic workflows", "Complex reasoning"],
        "badge": "Latest",
    },
    {
        "id": "gpt-5.2-pro-2025-12-11",
        "name": "GPT-5.2 Pro",
        "provider": "OpenAI",
        "category": "GPT-5 Series",
        "description": "Uses more compute for harder thinking on tough problems",
        "input_price": 21.00,
        "output_price": 168.00,
        "context_window": 400000,
        "best_for": ["Tough problems", "Deep reasoning", "High-stakes tasks"],
        "badge": "Premium",
    },
    {
        "id": "gpt-5.2-codex-2025-12-11",
        "name": "GPT-5.2 Codex",
        "provider": "OpenAI",
        "category": "GPT-5 Series",
        "description": "Coding-optimized variant for agentic coding workflows",
        "input_price": 1.75,
        "output_price": 14.00,
        "context_window": 400000,
        "best_for": ["Agentic coding", "Code generation", "Interactive coding"],
    },
    # Anthropic Claude
    {
        "id": "claude-opus-4-6",
        "name": "Claude Opus 4.6",
        "provider": "Anthropic",
        "category": "Claude",
        "description": "Most intelligent model for building agents and coding",
        "input_price": 5.00,
        "output_price": 25.00,
        "context_window": 200000,
        "best_for": ["Agents", "Complex coding", "Deep reasoning"],
        "badge": "Latest",
    },
    {
        "id": "claude-sonnet-4-6",
        "name": "Claude Sonnet 4.6",
        "provider": "Anthropic",
        "category": "Claude",
        "description": "Best combination of speed and intelligence",
        "input_price": 3.00,
        "output_price": 15.00,
        "context_window": 200000,
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
        "id": "gemini-3.1-pro-preview",
        "name": "Gemini 3.1 Pro",
        "provider": "Google",
        "category": "Gemini",
        "description": "Advanced intelligence with powerful agentic and coding capabilities",
        "input_price": 2.00,
        "output_price": 12.00,
        "context_window": 1000000,
        "best_for": ["Complex reasoning", "Agentic workflows", "Coding"],
        "badge": "Preview",
    },
    {
        "id": "gemini-3-pro-preview",
        "name": "Gemini 3 Pro",
        "provider": "Google",
        "category": "Gemini",
        "description": "State-of-the-art reasoning with advanced multimodal understanding",
        "input_price": 2.00,
        "output_price": 12.00,
        "context_window": 1000000,
        "best_for": ["Complex reasoning", "Multimodal tasks", "Agentic workflows"],
        "badge": "Preview",
    },
    {
        "id": "gemini-3-flash-preview",
        "name": "Gemini 3 Flash",
        "provider": "Google",
        "category": "Gemini",
        "description": "Frontier-class performance rivaling larger models at a fraction of the cost",
        "input_price": 0.50,
        "output_price": 3.00,
        "context_window": 1000000,
        "best_for": ["Fast reasoning", "Multimodal tasks", "Cost-effective"],
        "badge": "Preview",
    },
    {
        "id": "gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "provider": "Google",
        "category": "Gemini",
        "description": "Advanced model for complex tasks with deep reasoning and coding",
        "input_price": 1.25,
        "output_price": 10.00,
        "context_window": 1000000,
        "best_for": ["Analysis", "Science", "Education"],
    },
    {
        "id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "provider": "Google",
        "category": "Gemini",
        "description": "Best price-performance for low-latency reasoning tasks",
        "input_price": 0.30,
        "output_price": 2.50,
        "context_window": 1000000,
        "best_for": ["Quick tasks", "Summaries", "General queries"],
    },
    {
        "id": "gemini-2.5-flash-lite",
        "name": "Gemini 2.5 Flash-Lite",
        "provider": "Google",
        "category": "Gemini",
        "description": "Fastest and most budget-friendly multimodal model",
        "input_price": 0.10,
        "output_price": 0.40,
        "context_window": 1000000,
        "best_for": ["Simple questions", "High volume", "Quick lookups"],
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
        "context_window": 128000,
        "best_for": ["Current events", "Research", "Fact-checking"],
        "badge": "Web Search",
    },
]

def get_models_catalog():
    """Return the full models catalog for the frontend."""
    return MODELS_CATALOG

# Default encoding for token estimation
DEFAULT_ENCODING = "cl100k_base"  # Works for most modern models


def get_encoding_for_model(model: str) -> tiktoken.Encoding:
    """Get the appropriate tiktoken encoding for a model."""
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
    Calculate the actual cost in USD for a request.

    Args:
        model: Model identifier
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens

    Returns:
        Cost in USD (as float, e.g., 0.0015 for $0.0015)
    """
    pricing = get_model_pricing(model)

    # Convert from per-million to actual cost
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost


def calculate_cost_cents(model: str, input_tokens: int, output_tokens: int) -> int:
    """
    Calculate the actual cost in cents (for database storage).

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
