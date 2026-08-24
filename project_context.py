"""Load complete or retrieved project source context for model prompts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from project_prompt import segments_from_offsets
from project_store import ProjectStore


class ProjectContextError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProjectContext:
    project: dict[str, Any]
    sources: list[dict[str, Any]]
    draft: str


def _last_query(history: list[Any]) -> str:
    for message in reversed(history):
        role = getattr(message, "role", None)
        content = getattr(message, "content", None)
        if role is None and isinstance(message, dict):
            role = message.get("role")
            content = message.get("content")
        if role == "user":
            return str(content or "")
    return ""


def load_project_context(
    *,
    store: ProjectStore,
    bucket,
    rag,
    user_id: str,
    project_id: str,
    history: list[Any],
) -> ProjectContext:
    project = store.get_project_record(user_id, project_id)
    ready_sources = [
        source
        for source in store.list_sources(user_id, project_id)
        if source.get("status") == "ready"
    ]
    prompt_sources = [{**source, "segments": []} for source in ready_sources]

    if project.get("context_mode", "full") == "full":
        for source in prompt_sources:
            try:
                text = bucket.blob(source["text_path"]).download_as_text(encoding="utf-8")
                offsets = json.loads(
                    bucket.blob(source["pages_path"]).download_as_text(encoding="utf-8")
                )
            except Exception as error:
                raise ProjectContextError(
                    f"Could not load extracted text for source {source.get('source_num')}."
                ) from error
            source["segments"] = segments_from_offsets(text, offsets)
    elif ready_sources:
        if rag is None:
            raise ProjectContextError("Project retrieval is currently unavailable.")
        try:
            results = rag.search(
                user_id,
                _last_query(history),
                top_k=40,
                score_threshold=0.5,
                project_id=project_id,
            )
        except Exception as error:
            raise ProjectContextError("Project retrieval failed.") from error
        by_source = {source["id"]: source for source in prompt_sources}
        for result in results:
            source = by_source.get(result.get("source_id"))
            if not source:
                continue
            segment: dict[str, Any] = {"text": result.get("chunk_text", "")}
            if result.get("page") is not None:
                segment["page"] = result["page"]
            if result.get("paragraph") is not None:
                segment["paragraph"] = result["paragraph"]
            source["segments"].append(segment)

    draft = project.get("draft") or {}
    return ProjectContext(
        project=project,
        sources=prompt_sources,
        draft=str(draft.get("markdown", "")),
    )
