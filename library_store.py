"""School library registry and audience resolution (Postgres side).

The chunks live in the school's Qdrant collection; these rows say what was
indexed, from where, at which audience. Audience resolution mirrors the SQL
function ``romalume.user_audiences`` for callers that connect as the app
role (no ``auth.uid()``).
"""

from __future__ import annotations

from typing import Any

import db

AUDIENCES = ("staff", "marketing", "leadership", "board", "finance")


def get_school(client_id: str) -> dict | None:
    row = db.fetch_one(
        """
        select s.*, c.name from romalume.school_settings s
        join public.clients c on c.id = s.client_id
        where s.client_id = %s
        """,
        (client_id,),
    )
    if row:
        row = dict(row)
        row["client_id"] = str(row["client_id"])
    return row


def get_school_by_slug(slug: str) -> dict | None:
    row = db.fetch_one(
        """
        select s.*, c.name from romalume.school_settings s
        join public.clients c on c.id = s.client_id
        where s.slug = %s
        """,
        (slug.lower(),),
    )
    if row:
        row = dict(row)
        row["client_id"] = str(row["client_id"])
    return row


def user_audiences(user_id: str, client_id: str | None, *, is_super_admin: bool = False) -> list[str]:
    """Which audience tags this person may read at this school."""
    if is_super_admin:
        return list(AUDIENCES)
    if not client_id:
        return []
    rows = db.fetch_all(
        "select audience from romalume.member_audiences where client_id = %s and user_id = %s",
        (client_id, user_id),
    )
    granted = {r["audience"] for r in rows}
    return [a for a in AUDIENCES if a == "staff" or a in granted]


def upsert_document(client_id: str, *, source_path: str, title: str, audience: str,
                    qdrant_collection: str, chunk_count: int, source_system: str | None,
                    kind: str | None, url: str | None, last_modified: str | None,
                    content_hash: str, text_chars: int, uploaded_by: str | None = None,
                    error: str | None = None) -> dict:
    row = db.fetch_one(
        """
        insert into romalume.library_documents
          (client_id, uploaded_by, title, filename, source_path, audience, qdrant_collection,
           chunk_count, status, source_system, kind, url, last_modified, content_hash,
           text_chars, indexed_at, error)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s)
        on conflict (client_id, source_path) where source_path is not null do update set
          title = excluded.title, filename = excluded.filename, audience = excluded.audience,
          qdrant_collection = excluded.qdrant_collection, chunk_count = excluded.chunk_count,
          status = excluded.status, source_system = excluded.source_system, kind = excluded.kind,
          url = excluded.url, last_modified = excluded.last_modified,
          content_hash = excluded.content_hash, text_chars = excluded.text_chars,
          indexed_at = now(), error = excluded.error
        returning *
        """,
        (client_id, uploaded_by, title, source_path.rsplit("/", 1)[-1], source_path, audience,
         qdrant_collection, chunk_count, "indexed" if not error else "error", source_system, kind,
         url, last_modified, content_hash, text_chars, error),
    )
    return dict(row)


def existing_hashes(client_id: str) -> dict[str, str]:
    rows = db.fetch_all(
        "select source_path, content_hash from romalume.library_documents where client_id = %s and source_path is not null and status = 'indexed'",
        (client_id,),
    )
    return {r["source_path"]: r["content_hash"] for r in rows}


def list_documents(client_id: str, audiences: list[str]) -> list[dict[str, Any]]:
    if not audiences:
        return []
    rows = db.fetch_all(
        """
        select id::text as id, title, filename, audience, source_system, kind, url, last_modified,
               chunk_count, status, indexed_at
        from romalume.library_documents
        where client_id = %s and audience = any(%s) and status = 'indexed'
        order by audience, title
        """,
        (client_id, list(audiences)),
    )
    return [dict(r) for r in rows]


def summary(client_id: str, audiences: list[str] | None = None) -> dict:
    audience_filter = "and audience = any(%s)" if audiences is not None else ""
    params = (client_id, list(audiences)) if audiences is not None else (client_id,)
    row = db.fetch_one(
        f"""
        select count(*) filter (where status = 'indexed') as documents,
               coalesce(sum(chunk_count) filter (where status = 'indexed'), 0) as chunks,
               count(*) filter (where status = 'error') as errors,
               max(indexed_at) as last_indexed_at
        from romalume.library_documents where client_id = %s {audience_filter}
        """,
        params,
    )
    return dict(row or {})
