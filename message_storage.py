"""Pure helpers for keeping persisted chat history safe and bounded."""

import re
from typing import Iterable


MAX_STORED_MESSAGES = 50
MAX_STORED_MESSAGE_CHARS = 15_000
DATA_URI_PATTERN = re.compile(
    r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+"
)
ALLOWED_ROLES = {"user", "assistant", "context"}


def compact_messages_for_storage(messages: Iterable) -> list[dict]:
    """Drop internal roles/image bytes and enforce Firestore-safe history bounds."""
    compacted = []
    for message in list(messages)[-MAX_STORED_MESSAGES:]:
        item = message.model_dump() if hasattr(message, "model_dump") else dict(message)
        if item.get("role") not in ALLOWED_ROLES:
            continue
        content = DATA_URI_PATTERN.sub(
            "[Image omitted from saved history]",
            str(item.get("content", "")),
        )
        item["content"] = content[:MAX_STORED_MESSAGE_CHARS]
        item.pop("streaming", None)
        compacted.append(item)
    return compacted
