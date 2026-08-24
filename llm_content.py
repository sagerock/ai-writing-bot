"""Helpers for normalizing LLM message content across provider packages."""


def stream_chunk_text(content) -> str:
    """Extract text from a streamed chunk's content.

    Newer LangChain provider packages emit ``content`` as a list of blocks
    (``{"type": "text", "text": ...}``, ``{"type": "thinking", ...}``) rather
    than a plain string. Only text blocks are surfaced to the client.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type", "text") == "text":
                parts.append(block.get("text", "") or "")
        return "".join(parts)
    if content is None:
        return ""
    return str(content)
