"""Pure helpers for splitting indexed source text without crossing page boundaries."""

from __future__ import annotations

from typing import Any, Callable, Iterable


def split_source_chunks(
    text: str,
    split_text: Callable[[str], list[str]],
    offsets: Iterable[dict[str, Any]] | None = None,
) -> list[tuple[str, dict[str, int]]]:
    if not offsets:
        return [(chunk, {}) for chunk in split_text(text)]

    chunks: list[tuple[str, dict[str, int]]] = []
    for entry in offsets:
        start = max(0, int(entry.get("start", 0)))
        end = min(len(text), int(entry.get("end", len(text))))
        if end <= start:
            continue
        location = {}
        if "page" in entry:
            location["page"] = int(entry["page"])
        if "paragraph" in entry:
            location["paragraph"] = int(entry["paragraph"])
        chunks.extend((chunk, location) for chunk in split_text(text[start:end]))
    return chunks
