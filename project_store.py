"""Firestore persistence for memo projects.

The store is intentionally web-framework-free. Routes supply the authenticated
user ID, and every document path is rooted below that user's document.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from uuid import uuid4

from google.cloud.firestore_v1.transaction import transactional


MAX_DRAFT_VERSIONS = 50


class ProjectNotFound(LookupError):
    pass


class SourceNotFound(LookupError):
    pass


class ChatNotFound(LookupError):
    pass


class DraftVersionNotFound(LookupError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _with_id(snapshot) -> dict[str, Any]:
    data = snapshot.to_dict() or {}
    return {"id": snapshot.id, **data}


def _stream_sorted(collection, key: Callable[[dict[str, Any]], Any]) -> list[dict[str, Any]]:
    items = [_with_id(snapshot) for snapshot in collection.stream()]
    return sorted(items, key=key)


@transactional
def _reserve_source_transaction(
    transaction,
    project_ref,
    source_ref,
    source: dict[str, Any],
    now: datetime,
) -> int:
    project_snapshot = project_ref.get(transaction=transaction)
    if not project_snapshot.exists:
        raise ProjectNotFound(project_ref.id)
    project = project_snapshot.to_dict() or {}
    source_num = int(project.get("next_source_num", 1))
    source["source_num"] = source_num
    transaction.set(source_ref, source)
    transaction.update(
        project_ref,
        {"next_source_num": source_num + 1, "updated_at": now},
    )
    return source_num


@transactional
def _save_draft_transaction(
    transaction,
    project_ref,
    markdown: str,
    reason: str,
    now: datetime,
) -> dict[str, Any]:
    project_snapshot = project_ref.get(transaction=transaction)
    if not project_snapshot.exists:
        raise ProjectNotFound(project_ref.id)
    project = project_snapshot.to_dict() or {}
    current = project.get("draft") or {}
    version = int(current.get("version", 0)) + 1
    draft = {"markdown": markdown, "updated_at": now, "version": version}
    transaction.set(
        project_ref.collection("draft_versions").document(str(version)),
        {
            "version": version,
            "markdown": markdown,
            "saved_at": now,
            "reason": reason,
        },
    )
    transaction.update(project_ref, {"draft": draft, "updated_at": now})
    return draft


class ProjectStore:
    def __init__(
        self,
        db,
        *,
        full_context_tokens: int = 400_000,
        now: Callable[[], datetime] = _utc_now,
    ):
        self.db = db
        self.full_context_tokens = full_context_tokens
        self.now = now

    def _user_ref(self, user_id: str):
        return self.db.collection("users").document(user_id)

    def _projects(self, user_id: str):
        return self._user_ref(user_id).collection("projects")

    def _project_ref(self, user_id: str, project_id: str):
        return self._projects(user_id).document(project_id)

    def _require_project(self, user_id: str, project_id: str):
        snapshot = self._project_ref(user_id, project_id).get()
        if not snapshot.exists:
            raise ProjectNotFound(project_id)
        return snapshot

    def create_project(
        self,
        user_id: str,
        *,
        name: str,
        kind: str,
        charge: dict[str, str],
        default_model: str,
    ) -> dict[str, Any]:
        project_id = uuid4().hex
        now = self.now()
        data = {
            "name": name,
            "kind": kind,
            "charge": charge,
            "draft": {"markdown": "", "updated_at": now, "version": 0},
            "context_mode": "full",
            "default_model": default_model,
            "next_source_num": 1,
            "total_source_tokens": 0,
            "created_at": now,
            "updated_at": now,
            "archived": False,
        }
        self._project_ref(user_id, project_id).set(data)
        return {"id": project_id, **data}

    def list_projects(
        self, user_id: str, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        for snapshot in self._projects(user_id).stream():
            data = _with_id(snapshot)
            if data.get("archived", False) and not include_archived:
                continue
            project_ref = snapshot.reference
            sources = list(project_ref.collection("sources").stream())
            chats = list(project_ref.collection("chats").stream())
            draft = data.get("draft") or {}
            data["draft"] = {
                "version": int(draft.get("version", 0)),
                "updated_at": draft.get("updated_at"),
            }
            data.update(
                {
                    "source_count": len(sources),
                    "chat_count": len(chats),
                    "draft_word_count": len(str(draft.get("markdown", "")).split()),
                }
            )
            projects.append(data)
        return sorted(
            projects,
            key=lambda project: project.get("updated_at")
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

    def get_project(self, user_id: str, project_id: str) -> dict[str, Any]:
        snapshot = self._require_project(user_id, project_id)
        project_ref = snapshot.reference
        sources = _stream_sorted(
            project_ref.collection("sources"),
            key=lambda source: source.get("source_num", 0),
        )
        chat_summaries = project_ref.collection("chats").select(
            ["title", "mode", "model", "message_count", "created_at", "updated_at"]
        )
        chats = _stream_sorted(
            chat_summaries,
            key=lambda chat: chat.get("updated_at") or datetime.min.replace(tzinfo=timezone.utc),
        )
        chats.reverse()
        return {**_with_id(snapshot), "sources": sources, "chats": chats}

    def get_project_record(self, user_id: str, project_id: str) -> dict[str, Any]:
        return _with_id(self._require_project(user_id, project_id))

    def update_project(
        self, user_id: str, project_id: str, changes: dict[str, Any]
    ) -> dict[str, Any]:
        self._require_project(user_id, project_id)
        update = {**changes, "updated_at": self.now()}
        self._project_ref(user_id, project_id).update(update)
        return _with_id(self._project_ref(user_id, project_id).get())

    def archive_project(self, user_id: str, project_id: str) -> dict[str, Any]:
        return self.update_project(user_id, project_id, {"archived": True})

    def reserve_source(
        self,
        user_id: str,
        project_id: str,
        *,
        filename: str,
        content_type: str,
        size: int,
        label: str,
    ) -> dict[str, Any]:
        project_ref = self._project_ref(user_id, project_id)
        source_id = uuid4().hex
        now = self.now()
        source = {
            "filename": filename,
            "content_type": content_type,
            "size": size,
            "label": label,
            "source_num": 0,
            "pages": None,
            "text_chars": 0,
            "estimated_tokens": 0,
            "status": "processing",
            "indexed": False,
            "chunk_count": 0,
            "indexing_error": None,
            "uploaded_at": now,
        }
        _reserve_source_transaction(
            self.db.transaction(),
            project_ref,
            project_ref.collection("sources").document(source_id),
            source,
            now,
        )
        return {"id": source_id, **source}

    def finalize_source(
        self,
        user_id: str,
        project_id: str,
        source_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_project(user_id, project_id)
        source_ref = (
            self._project_ref(user_id, project_id)
            .collection("sources")
            .document(source_id)
        )
        if not source_ref.get().exists:
            raise SourceNotFound(source_id)
        source_ref.update({**changes, "status": "ready"})
        self.recompute_context_mode(user_id, project_id)
        return _with_id(source_ref.get())

    def fail_source(
        self,
        user_id: str,
        project_id: str,
        source_id: str,
        error: str,
        changes: dict[str, Any] | None = None,
    ) -> None:
        source_ref = (
            self._project_ref(user_id, project_id)
            .collection("sources")
            .document(source_id)
        )
        if source_ref.get().exists:
            source_ref.update(
                {
                    **(changes or {}),
                    "status": "error",
                    "indexing_error": error[:2000],
                }
            )

    def get_source(self, user_id: str, project_id: str, source_id: str) -> dict[str, Any]:
        self._require_project(user_id, project_id)
        snapshot = (
            self._project_ref(user_id, project_id)
            .collection("sources")
            .document(source_id)
            .get()
        )
        if not snapshot.exists:
            raise SourceNotFound(source_id)
        return _with_id(snapshot)

    def update_source_label(
        self, user_id: str, project_id: str, source_id: str, label: str
    ) -> dict[str, Any]:
        source = self.get_source(user_id, project_id, source_id)
        source_ref = (
            self._project_ref(user_id, project_id)
            .collection("sources")
            .document(source_id)
        )
        source_ref.update({"label": label})
        self._project_ref(user_id, project_id).update({"updated_at": self.now()})
        return {**source, "label": label}

    def delete_source(self, user_id: str, project_id: str, source_id: str) -> None:
        self.get_source(user_id, project_id, source_id)
        self._project_ref(user_id, project_id).collection("sources").document(source_id).delete()
        self.recompute_context_mode(user_id, project_id)

    def recompute_context_mode(self, user_id: str, project_id: str) -> dict[str, Any]:
        project_ref = self._project_ref(user_id, project_id)
        self._require_project(user_id, project_id)
        total_tokens = 0
        for snapshot in project_ref.collection("sources").stream():
            source = snapshot.to_dict() or {}
            if source.get("status") != "ready":
                continue
            total_tokens += int(
                source.get("estimated_tokens")
                or max(0, int(source.get("text_chars", 0)) // 4)
            )
        context_mode = "full" if total_tokens <= self.full_context_tokens else "retrieval"
        project_ref.update(
            {
                "total_source_tokens": total_tokens,
                "context_mode": context_mode,
                "updated_at": self.now(),
            }
        )
        return {"context_mode": context_mode, "total_source_tokens": total_tokens}

    def get_draft(self, user_id: str, project_id: str) -> dict[str, Any]:
        project = _with_id(self._require_project(user_id, project_id))
        return project.get("draft") or {"markdown": "", "version": 0, "updated_at": None}

    def save_draft(
        self,
        user_id: str,
        project_id: str,
        *,
        markdown: str,
        reason: str,
    ) -> dict[str, Any]:
        project_ref = self._project_ref(user_id, project_id)
        now = self.now()
        draft = _save_draft_transaction(
            self.db.transaction(),
            project_ref,
            markdown,
            reason,
            now,
        )
        self._cap_draft_versions(project_ref)
        return draft

    def _cap_draft_versions(self, project_ref) -> None:
        versions = list(project_ref.collection("draft_versions").stream())
        versions.sort(key=lambda snapshot: int((snapshot.to_dict() or {}).get("version", 0)))
        for snapshot in versions[:-MAX_DRAFT_VERSIONS]:
            snapshot.reference.delete()

    def list_draft_versions(self, user_id: str, project_id: str) -> list[dict[str, Any]]:
        project_ref = self._project_ref(user_id, project_id)
        self._require_project(user_id, project_id)
        versions = [
            _with_id(snapshot)
            for snapshot in project_ref.collection("draft_versions").stream()
        ]
        return sorted(versions, key=lambda item: int(item.get("version", 0)), reverse=True)

    def restore_draft(
        self, user_id: str, project_id: str, version: int
    ) -> dict[str, Any]:
        project_ref = self._project_ref(user_id, project_id)
        self._require_project(user_id, project_id)
        version_snapshot = project_ref.collection("draft_versions").document(str(version)).get()
        if not version_snapshot.exists:
            raise DraftVersionNotFound(str(version))
        version_data = version_snapshot.to_dict() or {}
        return self.save_draft(
            user_id,
            project_id,
            markdown=str(version_data.get("markdown", "")),
            reason=f"restored version {version}",
        )

    def create_chat(
        self,
        user_id: str,
        project_id: str,
        *,
        title: str,
        mode: str,
        model: str | None,
    ) -> dict[str, Any]:
        project = _with_id(self._require_project(user_id, project_id))
        chat_id = uuid4().hex
        now = self.now()
        chat = {
            "title": title,
            "mode": mode,
            "model": model or project.get("default_model", "claude-sonnet-5"),
            "messages": [],
            "message_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        self._project_ref(user_id, project_id).collection("chats").document(chat_id).set(chat)
        self._project_ref(user_id, project_id).update({"updated_at": now})
        return {"id": chat_id, **chat}

    def get_chat(self, user_id: str, project_id: str, chat_id: str) -> dict[str, Any]:
        self._require_project(user_id, project_id)
        snapshot = (
            self._project_ref(user_id, project_id)
            .collection("chats")
            .document(chat_id)
            .get()
        )
        if not snapshot.exists:
            raise ChatNotFound(chat_id)
        return _with_id(snapshot)

    def save_chat(
        self,
        user_id: str,
        project_id: str,
        chat_id: str,
        *,
        messages: Iterable[dict[str, Any]],
        mode: str,
        model: str,
        title: str | None = None,
    ) -> dict[str, Any]:
        self.get_chat(user_id, project_id, chat_id)
        now = self.now()
        stored_messages = list(messages)
        update: dict[str, Any] = {
            "messages": stored_messages,
            "message_count": len(stored_messages),
            "mode": mode,
            "model": model,
            "updated_at": now,
        }
        if title:
            update["title"] = title
        chat_ref = self._project_ref(user_id, project_id).collection("chats").document(chat_id)
        chat_ref.update(update)
        self._project_ref(user_id, project_id).update({"updated_at": now})
        return _with_id(chat_ref.get())

    def delete_chat(self, user_id: str, project_id: str, chat_id: str) -> None:
        self.get_chat(user_id, project_id, chat_id)
        self._project_ref(user_id, project_id).collection("chats").document(chat_id).delete()
        self._project_ref(user_id, project_id).update({"updated_at": self.now()})
