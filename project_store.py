"""Postgres persistence for memo projects (Supabase, ``romalume`` schema).

The store is web-framework-free. Routes supply the authenticated user ID;
every row is scoped by ``user_id`` (and optionally ``client_id`` for school
projects). The public API matches the Firestore store it replaced on
2026-09-20 so the routers did not change.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

import db

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


def _draft(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "markdown": row.get("draft_markdown") or "",
        "version": int(row.get("draft_version") or 0),
        "updated_at": row.get("draft_saved_at"),
    }


def _project_out(row: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in row.items() if not k.startswith("draft_")}
    out["id"] = str(row["id"])
    out["draft"] = _draft(row)
    return out


def _row_out(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["id"] = str(row["id"])
    for key in ("project_id", "user_id", "client_id"):
        if out.get(key) is not None:
            out[key] = str(out[key])
    return out


class ProjectStore:
    def __init__(
        self,
        _db=None,
        *,
        full_context_tokens: int = 400_000,
        now: Callable[[], datetime] = _utc_now,
    ):
        self.full_context_tokens = full_context_tokens
        self.now = now

    # ------------------------------------------------------------ projects

    def _require_project(self, user_id: str, project_id: str, conn=None) -> dict[str, Any]:
        row = db.fetch_one(
            "select * from romalume.projects where id = %s and user_id = %s",
            (project_id, user_id),
            conn=conn,
        )
        if not row:
            raise ProjectNotFound(project_id)
        return row

    def create_project(
        self,
        user_id: str,
        *,
        name: str,
        kind: str,
        charge: dict[str, str],
        default_model: str,
        initial_draft: str = "",
        client_id: str | None = None,
        owner_kind: str = "user",
    ) -> dict[str, Any]:
        now = self.now()
        row = db.fetch_one(
            """
            insert into romalume.projects
              (user_id, client_id, owner_kind, name, kind, charge, context_mode,
               default_model, draft_markdown, draft_version, draft_saved_at,
               next_source_num, total_source_tokens, created_at, updated_at, archived)
            values (%s, %s, %s, %s, %s, %s, 'full', %s, %s, 0, %s, 1, 0, %s, %s, false)
            returning *
            """,
            (user_id, client_id, owner_kind, name, kind, db.jsonb(charge),
             default_model, initial_draft, now, now, now),
        )
        return _project_out(row)

    def list_projects(
        self, user_id: str, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        rows = db.fetch_all(
            """
            select p.*,
                   (select count(*) from romalume.sources s where s.project_id = p.id) as source_count,
                   (select count(*) from romalume.conversations c where c.project_id = p.id) as chat_count
            from romalume.projects p
            where p.user_id = %s and (%s or not p.archived)
            order by p.updated_at desc nulls last
            """,
            (user_id, include_archived),
        )
        out = []
        for row in rows:
            project = _project_out(row)
            project["draft_word_count"] = len((row.get("draft_markdown") or "").split())
            project["draft"] = {"version": project["draft"]["version"], "updated_at": project["draft"]["updated_at"]}
            out.append(project)
        return out

    def get_project(self, user_id: str, project_id: str) -> dict[str, Any]:
        row = self._require_project(user_id, project_id)
        sources = self.list_sources(user_id, project_id)
        chats = [
            _row_out(c)
            for c in db.fetch_all(
                """
                select id, title, mode, model, message_count, created_at, updated_at
                from romalume.conversations where project_id = %s
                order by updated_at desc nulls last
                """,
                (project_id,),
            )
        ]
        return {**_project_out(row), "sources": sources, "chats": chats}

    def get_project_record(self, user_id: str, project_id: str) -> dict[str, Any]:
        return _project_out(self._require_project(user_id, project_id))

    def list_sources(self, user_id: str, project_id: str) -> list[dict[str, Any]]:
        self._require_project(user_id, project_id)
        return [
            _row_out(r)
            for r in db.fetch_all(
                "select * from romalume.sources where project_id = %s order by source_num",
                (project_id,),
            )
        ]

    _PROJECT_COLUMNS = {
        "name", "kind", "charge", "context_mode", "default_model", "archived",
        "client_id", "owner_kind",
    }

    def update_project(
        self, user_id: str, project_id: str, changes: dict[str, Any]
    ) -> dict[str, Any]:
        self._require_project(user_id, project_id)
        sets, params = [], []
        for key, value in changes.items():
            if key not in self._PROJECT_COLUMNS:
                continue
            sets.append(f"{key} = %s")
            params.append(db.jsonb(value) if key == "charge" else value)
        sets.append("updated_at = %s")
        params.append(self.now())
        params.extend([project_id, user_id])
        row = db.fetch_one(
            f"update romalume.projects set {', '.join(sets)} where id = %s and user_id = %s returning *",
            params,
        )
        return _project_out(row)

    def archive_project(self, user_id: str, project_id: str) -> dict[str, Any]:
        return self.update_project(user_id, project_id, {"archived": True})

    # ------------------------------------------------------------- sources

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
        now = self.now()
        with db.transaction() as conn:
            project = db.fetch_one(
                "select * from romalume.projects where id = %s and user_id = %s for update",
                (project_id, user_id),
                conn=conn,
            )
            if not project:
                raise ProjectNotFound(project_id)
            source_num = int(project.get("next_source_num") or 1)
            row = db.fetch_one(
                """
                insert into romalume.sources
                  (project_id, client_id, source_num, label, filename, content_type, size,
                   status, indexed, chunk_count, text_chars, estimated_tokens, uploaded_at)
                values (%s, %s, %s, %s, %s, %s, %s, 'processing', false, 0, 0, 0, %s)
                returning *
                """,
                (project_id, project.get("client_id"), source_num, label, filename,
                 content_type, size, now),
                conn=conn,
            )
            db.execute(
                "update romalume.projects set next_source_num = %s, updated_at = %s where id = %s",
                (source_num + 1, now, project_id),
                conn=conn,
            )
        return _row_out(row)

    _SOURCE_COLUMNS = {
        "label", "storage_path", "text_path", "pages_path", "pages", "paragraphs",
        "map_kind", "text_chars", "estimated_tokens", "indexed", "chunk_count",
        "indexing_error", "status",
    }

    def _update_source(self, project_id: str, source_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
        sets, params = [], []
        for key, value in changes.items():
            if key in self._SOURCE_COLUMNS:
                sets.append(f"{key} = %s")
                params.append(value)
        if not sets:
            return db.fetch_one(
                "select * from romalume.sources where id = %s and project_id = %s",
                (source_id, project_id),
            )
        params.extend([source_id, project_id])
        return db.fetch_one(
            f"update romalume.sources set {', '.join(sets)} where id = %s and project_id = %s returning *",
            params,
        )

    def finalize_source(
        self,
        user_id: str,
        project_id: str,
        source_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_project(user_id, project_id)
        row = self._update_source(project_id, source_id, {**changes, "status": "ready"})
        if not row:
            raise SourceNotFound(source_id)
        self.recompute_context_mode(user_id, project_id)
        return _row_out(row)

    def fail_source(
        self,
        user_id: str,
        project_id: str,
        source_id: str,
        error: str,
        changes: dict[str, Any] | None = None,
    ) -> None:
        self._update_source(
            project_id, source_id,
            {**(changes or {}), "status": "error", "indexing_error": error[:2000]},
        )

    def get_source(self, user_id: str, project_id: str, source_id: str) -> dict[str, Any]:
        self._require_project(user_id, project_id)
        row = db.fetch_one(
            "select * from romalume.sources where id = %s and project_id = %s",
            (source_id, project_id),
        )
        if not row:
            raise SourceNotFound(source_id)
        return _row_out(row)

    def update_source_label(
        self, user_id: str, project_id: str, source_id: str, label: str
    ) -> dict[str, Any]:
        source = self.get_source(user_id, project_id, source_id)
        self._update_source(project_id, source_id, {"label": label})
        db.execute(
            "update romalume.projects set updated_at = %s where id = %s",
            (self.now(), project_id),
        )
        return {**source, "label": label}

    def delete_source(self, user_id: str, project_id: str, source_id: str) -> None:
        self.get_source(user_id, project_id, source_id)
        db.execute(
            "delete from romalume.sources where id = %s and project_id = %s",
            (source_id, project_id),
        )
        self.recompute_context_mode(user_id, project_id)

    def recompute_context_mode(self, user_id: str, project_id: str) -> dict[str, Any]:
        self._require_project(user_id, project_id)
        row = db.fetch_one(
            """
            select coalesce(sum(coalesce(nullif(estimated_tokens, 0), greatest(0, coalesce(text_chars, 0) / 4))), 0)::int as total
            from romalume.sources where project_id = %s and status = 'ready'
            """,
            (project_id,),
        )
        total_tokens = int(row["total"] if row else 0)
        context_mode = "full" if total_tokens <= self.full_context_tokens else "retrieval"
        db.execute(
            """
            update romalume.projects
            set total_source_tokens = %s, context_mode = %s, updated_at = %s
            where id = %s
            """,
            (total_tokens, context_mode, self.now(), project_id),
        )
        return {"context_mode": context_mode, "total_source_tokens": total_tokens}

    # -------------------------------------------------------------- drafts

    def get_draft(self, user_id: str, project_id: str) -> dict[str, Any]:
        return _draft(self._require_project(user_id, project_id))

    def save_draft(
        self,
        user_id: str,
        project_id: str,
        *,
        markdown: str,
        reason: str,
    ) -> dict[str, Any]:
        now = self.now()
        with db.transaction() as conn:
            project = db.fetch_one(
                "select * from romalume.projects where id = %s and user_id = %s for update",
                (project_id, user_id),
                conn=conn,
            )
            if not project:
                raise ProjectNotFound(project_id)
            version = int(project.get("draft_version") or 0) + 1
            db.execute(
                """
                insert into romalume.draft_versions (project_id, client_id, version, markdown, reason, saved_at)
                values (%s, %s, %s, %s, %s, %s)
                """,
                (project_id, project.get("client_id"), version, markdown, reason, now),
                conn=conn,
            )
            db.execute(
                """
                update romalume.projects
                set draft_markdown = %s, draft_version = %s, draft_saved_at = %s, updated_at = %s
                where id = %s
                """,
                (markdown, version, now, now, project_id),
                conn=conn,
            )
            db.execute(
                """
                delete from romalume.draft_versions
                where project_id = %s and version <= %s - %s
                """,
                (project_id, version, MAX_DRAFT_VERSIONS),
                conn=conn,
            )
        return {"markdown": markdown, "updated_at": now, "version": version}

    def list_draft_versions(self, user_id: str, project_id: str) -> list[dict[str, Any]]:
        self._require_project(user_id, project_id)
        return [
            _row_out(r)
            for r in db.fetch_all(
                """
                select id, version, markdown, reason, saved_at
                from romalume.draft_versions where project_id = %s order by version desc
                """,
                (project_id,),
            )
        ]

    def restore_draft(
        self, user_id: str, project_id: str, version: int
    ) -> dict[str, Any]:
        self._require_project(user_id, project_id)
        row = db.fetch_one(
            "select markdown from romalume.draft_versions where project_id = %s and version = %s",
            (project_id, version),
        )
        if not row:
            raise DraftVersionNotFound(str(version))
        return self.save_draft(
            user_id, project_id,
            markdown=str(row.get("markdown") or ""),
            reason=f"restored version {version}",
        )

    # --------------------------------------------------------------- chats

    def create_chat(
        self,
        user_id: str,
        project_id: str,
        *,
        title: str,
        mode: str,
        model: str | None,
    ) -> dict[str, Any]:
        project = self._require_project(user_id, project_id)
        now = self.now()
        row = db.fetch_one(
            """
            insert into romalume.conversations
              (client_id, user_id, project_id, title, mode, model, messages, message_count,
               archived, created_at, updated_at)
            values (%s, %s, %s, %s, %s, %s, '[]'::jsonb, 0, false, %s, %s)
            returning *
            """,
            (project.get("client_id"), user_id, project_id, title, mode,
             model or project.get("default_model") or "claude-sonnet-5", now, now),
        )
        db.execute("update romalume.projects set updated_at = %s where id = %s", (now, project_id))
        return _row_out(row)

    def get_chat(self, user_id: str, project_id: str, chat_id: str) -> dict[str, Any]:
        self._require_project(user_id, project_id)
        row = db.fetch_one(
            "select * from romalume.conversations where id = %s and project_id = %s",
            (chat_id, project_id),
        )
        if not row:
            raise ChatNotFound(chat_id)
        return _row_out(row)

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
        stored = list(messages)
        row = db.fetch_one(
            """
            update romalume.conversations
            set messages = %s, message_count = %s, mode = %s, model = %s,
                title = coalesce(%s, title), updated_at = %s
            where id = %s and project_id = %s
            returning *
            """,
            (db.jsonb(stored), len(stored), mode, model, title, now, chat_id, project_id),
        )
        db.execute("update romalume.projects set updated_at = %s where id = %s", (now, project_id))
        return _row_out(row)

    def delete_chat(self, user_id: str, project_id: str, chat_id: str) -> None:
        self.get_chat(user_id, project_id, chat_id)
        db.execute(
            "delete from romalume.conversations where id = %s and project_id = %s",
            (chat_id, project_id),
        )
        db.execute(
            "update romalume.projects set updated_at = %s where id = %s",
            (self.now(), project_id),
        )
