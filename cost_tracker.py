"""
Cost tracking module for RomaLume.
Estimates token counts and calculates actual AI costs for transparent billing.
"""

import tiktoken
from typing import Optional

# Pricing per 1 MILLION tokens (as of December 2024)
# Format: {"input": price_per_1M_input, "output": price_per_1M_output}
MODEL_PRICING = {
    # OpenAI GPT-5 family
    "gpt-5-nano": {"input": 0.05, "output": 0.40},
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
    "gpt-5": {"input": 1.00, "output": 4.00},
    "gpt-5-pro": {"input": 3.00, "output": 12.00},
    "gpt-5.1": {"input": 1.25, "output": 5.00},

    # OpenAI GPT-4 family (legacy)
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},

    # Anthropic Claude
    "claude-opus-4-5": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
    "claude-opus-4-1": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},

    # Google Gemini
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-3-pro": {"input": 1.50, "output": 6.00},

    # Cohere
    "command-r-plus": {"input": 2.50, "output": 10.00},
    "command-r": {"input": 0.15, "output": 0.60},

    # Perplexity
    "sonar-pro": {"input": 3.00, "output": 15.00},
    "sonar": {"input": 1.00, "output": 1.00},
}

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
