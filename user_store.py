"""User records, documents, conversations, usage, and admin queries in Postgres.

Replaces the Firestore ``users/{uid}`` document and its subcollections
(2026-09-20). Identity comes from Supabase Auth; a ``romalume.user_settings``
row is created the first time a user is seen.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import db
from message_storage import compact_messages_for_storage

INITIAL_CREDITS = 100


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _out(row: dict | None) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for key in ("id", "user_id", "client_id", "project_id"):
        if out.get(key) is not None:
            out[key] = str(out[key])
    return out


# ------------------------------------------------------------------ users

def ensure_user(user_id: str, email: str | None = None, conn=None) -> dict:
    row = db.fetch_one(
        """
        insert into romalume.user_settings (user_id, email, credits, credits_used, subscription_status, last_seen_at)
        values (%s, %s, %s, 0, 'none', now())
        on conflict (user_id) do update
          set email = coalesce(excluded.email, romalume.user_settings.email),
              last_seen_at = now()
        returning *
        """,
        (user_id, email, INITIAL_CREDITS),
        conn=conn,
    )
    return _out(row)


def get_user(user_id: str, conn=None) -> dict | None:
    return _out(db.fetch_one("select * from romalume.user_settings where user_id = %s", (user_id,), conn=conn))


def get_user_by_stripe_customer(customer_id: str) -> dict | None:
    return _out(db.fetch_one(
        "select * from romalume.user_settings where stripe_customer_id = %s limit 1", (customer_id,)
    ))


_JSON_COLUMNS = {"profile", "email_preferences", "chat_settings"}
_USER_COLUMNS = {
    "email", "display_name", "client_id", "profile", "default_model", "credits",
    "credits_used", "subscription_status", "comped", "comped_reason",
    "stripe_customer_id", "stripe_subscription_id", "subscription_amount",
    "subscription_current_period_end", "daily_usage_date", "daily_requests",
    "all_time_ai_cost_cents", "all_time_requests", "all_time_charity_cents",
    "email_preferences", "chat_settings", "unsubscribed", "profile_updated_at",
}


def update_user(user_id: str, conn=None, **fields: Any) -> dict | None:
    sets, params = [], []
    for key, value in fields.items():
        if key not in _USER_COLUMNS:
            raise ValueError(f"unknown user column {key}")
        sets.append(f"{key} = %s")
        params.append(db.jsonb(value) if key in _JSON_COLUMNS else value)
    if not sets:
        return get_user(user_id, conn=conn)
    params.append(user_id)
    ensure_user(user_id, conn=conn)
    return _out(db.fetch_one(
        f"update romalume.user_settings set {', '.join(sets)} where user_id = %s returning *",
        params, conn=conn,
    ))


def increment_user(user_id: str, conn=None, **deltas: Any) -> dict | None:
    sets, params = [], []
    for key, delta in deltas.items():
        if key not in _USER_COLUMNS:
            raise ValueError(f"unknown user column {key}")
        sets.append(f"{key} = coalesce({key}, 0) + %s")
        params.append(delta)
    params.append(user_id)
    ensure_user(user_id, conn=conn)
    return _out(db.fetch_one(
        f"update romalume.user_settings set {', '.join(sets)} where user_id = %s returning *",
        params, conn=conn,
    ))


def lock_user(user_id: str, conn) -> dict:
    """Row-lock a user inside a transaction (creating it if needed)."""
    row = db.fetch_one(
        "select * from romalume.user_settings where user_id = %s for update", (user_id,), conn=conn
    )
    if row is None:
        row = ensure_user(user_id, conn=conn)
        row = db.fetch_one(
            "select * from romalume.user_settings where user_id = %s for update", (user_id,), conn=conn
        )
    return _out(row)


def list_users() -> list[dict]:
    """Every Supabase auth user, merged with their RomaLume settings and admin role."""
    rows = db.fetch_all(
        """
        select u.id as uid, u.email,
               coalesce(s.display_name, u.display_name, '') as display_name,
               coalesce(s.credits, %s) as credits, coalesce(s.credits_used, 0) as credits_used,
               coalesce(s.subscription_status, 'none') as subscription_status,
               coalesce(s.comped, false) as comped,
               exists (select 1 from public.admin_users a where a.user_id = u.id and a.role = 'super_admin') as is_admin,
               u.created_at, u.last_sign_in_at, s.last_seen_at
        from romalume.auth_users() u
        left join romalume.user_settings s on s.user_id = u.id
        order by u.created_at desc
        """,
        (INITIAL_CREDITS,),
    )
    return [_out(r) | {"uid": str(r["uid"])} for r in rows]


def get_auth_user(user_id: str) -> dict | None:
    return _out(db.fetch_one(
        "select * from romalume.auth_users() where id = %s",
        (user_id,),
    ))


def set_super_admin(user_id: str, is_admin: bool) -> None:
    """Grant or revoke super_admin in public.admin_users (the shared role table)."""
    if is_admin:
        email = (get_auth_user(user_id) or {}).get("email") or ""
        db.execute(
            """
            insert into public.admin_users (user_id, email, role)
            values (%s, %s, 'super_admin')
            on conflict do nothing
            """,
            (user_id, email),
        )
        db.execute(
            "update public.admin_users set role = 'super_admin' where user_id = %s and role <> 'super_admin' and client_id is null",
            (user_id,),
        )
    else:
        db.execute("delete from public.admin_users where user_id = %s and role = 'super_admin'", (user_id,))


# -------------------------------------------------------------- documents

def upsert_document(user_id: str, *, filename: str, storage_path: str, content_type: str | None,
                    size: int, project_name: str, indexed: bool, chunk_count: int,
                    indexing_error: str | None, client_id: str | None = None) -> dict:
    return _out(db.fetch_one(
        """
        insert into romalume.documents
          (user_id, client_id, filename, storage_path, content_type, size, project_name,
           indexed, chunk_count, indexing_error, uploaded_at)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        on conflict (user_id, filename) do update
          set storage_path = excluded.storage_path, content_type = excluded.content_type,
              size = excluded.size, project_name = excluded.project_name,
              indexed = excluded.indexed, chunk_count = excluded.chunk_count,
              indexing_error = excluded.indexing_error, uploaded_at = now()
        returning *
        """,
        (user_id, client_id, filename, storage_path, content_type, size, project_name,
         indexed, chunk_count, indexing_error),
    ))


def list_documents(user_id: str) -> list[dict]:
    return [_out(r) for r in db.fetch_all(
        "select * from romalume.documents where user_id = %s order by uploaded_at desc", (user_id,)
    )]


def get_document(user_id: str, filename: str) -> dict | None:
    return _out(db.fetch_one(
        "select * from romalume.documents where user_id = %s and filename = %s", (user_id, filename)
    ))


def delete_document(user_id: str, filename: str) -> bool:
    return db.execute(
        "delete from romalume.documents where user_id = %s and filename = %s", (user_id, filename)
    ) > 0


def document_api_shape(row: dict) -> dict:
    """The camelCase shape the frontend has always received."""
    uploaded = row.get("uploaded_at")
    return {
        "storagePath": row.get("storage_path"),
        "filename": row.get("filename"),
        "contentType": row.get("content_type"),
        "size": row.get("size"),
        "projectName": row.get("project_name") or "General",
        "uploadedAt": uploaded.isoformat() if hasattr(uploaded, "isoformat") else uploaded,
        "indexed": bool(row.get("indexed")),
        "chunkCount": row.get("chunk_count") or 0,
        "indexingError": row.get("indexing_error"),
    }


# ---------------------------------------------------- current conversation

def get_current_messages(user_id: str) -> list[dict]:
    row = db.fetch_one(
        "select messages from romalume.conversations where user_id = %s and mode = 'current' and project_id is null",
        (user_id,),
    )
    return compact_messages_for_storage(row["messages"] if row else [])


def save_current_messages(user_id: str, messages: Iterable[dict]) -> None:
    stored = compact_messages_for_storage(list(messages))
    db.execute(
        """
        insert into romalume.conversations (user_id, mode, messages, message_count, created_at, updated_at)
        values (%s, 'current', %s, %s, now(), now())
        on conflict (user_id) where mode = 'current' and project_id is null
        do update set messages = excluded.messages, message_count = excluded.message_count, updated_at = now()
        """,
        (user_id, db.jsonb(stored), len(stored)),
    )


# --------------------------------------------------------------- archives

def create_archive(user_id: str, *, archive_id: str, project_name: str, model: str | None,
                   messages: Iterable[dict]) -> dict:
    stored = compact_messages_for_storage(list(messages))
    return _out(db.fetch_one(
        """
        insert into romalume.conversations
          (user_id, mode, title, project_name, model, messages, message_count,
           archived, archived_at, created_at, updated_at)
        values (%s, 'archive', %s, %s, %s, %s, %s, true, now(), now(), now())
        returning *
        """,
        (user_id, archive_id, project_name, model, db.jsonb(stored), len(stored)),
    ))


def list_archives(user_id: str, *, limit: int | None = None) -> list[dict]:
    sql = """
        select * from romalume.conversations
        where user_id = %s and archived and project_id is null
        order by archived_at desc nulls last
    """
    params: list[Any] = [user_id]
    if limit:
        sql += " limit %s"
        params.append(limit)
    return [_out(r) for r in db.fetch_all(sql, params)]


def count_archives(user_id: str) -> int:
    row = db.fetch_one(
        "select count(*) as n from romalume.conversations where user_id = %s and archived and project_id is null",
        (user_id,),
    )
    return int(row["n"]) if row else 0


def get_archive(user_id: str, archive_id: str) -> dict | None:
    return _out(db.fetch_one(
        """
        select * from romalume.conversations
        where user_id = %s and archived and project_id is null and (id::text = %s or title = %s)
        limit 1
        """,
        (user_id, archive_id, archive_id),
    ))


def delete_archive(user_id: str, archive_id: str) -> bool:
    return db.execute(
        """
        delete from romalume.conversations
        where user_id = %s and archived and project_id is null and (id::text = %s or title = %s)
        """,
        (user_id, archive_id, archive_id),
    ) > 0


# ------------------------------------------------------------------ usage

def log_usage(*, user_id: str, model: str, original_model: str | None, routed_category: str | None,
              search_web: bool, search_docs: bool, input_tokens: int, output_tokens: int,
              cost_cents: float, client_id: str | None = None) -> None:
    with db.transaction() as conn:
        db.execute(
            """
            insert into romalume.usage_logs
              (client_id, user_id, model, original_model, routed_category, search_web, search_docs,
               input_tokens, output_tokens, cost_cents, estimated_cost_cents, created_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            """,
            (client_id, user_id, model, original_model, routed_category, search_web, search_docs,
             input_tokens, output_tokens, cost_cents, cost_cents),
            conn=conn,
        )
        increment_user(user_id, conn=conn, all_time_ai_cost_cents=cost_cents, all_time_requests=1)


def month_usage(user_id: str, month: str) -> dict:
    row = db.fetch_one(
        "select * from romalume.user_monthly_usage where user_id = %s and month = %s", (user_id, month)
    )
    return {
        "total_ai_cost_cents": float(row["total_ai_cost_cents"]) if row else 0.0,
        "total_requests": int(row["total_requests"]) if row else 0,
        "total_input_tokens": int(row["total_input_tokens"]) if row else 0,
        "total_output_tokens": int(row["total_output_tokens"]) if row else 0,
    }


def usage_overview() -> dict:
    row = db.fetch_one(
        """
        select count(*) as total,
               count(*) filter (where created_at >= date_trunc('day', now())) as today,
               count(*) filter (where created_at >= now() - interval '7 days') as week,
               count(*) filter (where created_at >= now() - interval '30 days') as month,
               count(distinct user_id) filter (where created_at >= date_trunc('day', now())) as users_today,
               count(distinct user_id) as users_total
        from romalume.usage_logs
        """
    )
    return dict(row or {})


def usage_by_model(days: int | None = None) -> list[dict]:
    sql = "select model, count(*) as requests, count(distinct user_id) as users from romalume.usage_logs"
    params: list[Any] = []
    if days:
        sql += " where created_at >= now() - (%s || ' days')::interval"
        params.append(str(days))
    sql += " group by model order by requests desc"
    return db.fetch_all(sql, params)


def usage_by_day(days: int) -> list[dict]:
    return db.fetch_all(
        """
        select to_char(created_at at time zone 'UTC', 'YYYY-MM-DD') as date,
               count(*) as requests, count(distinct user_id) as users
        from romalume.usage_logs
        where created_at >= now() - (%s || ' days')::interval
        group by 1 order by 1
        """,
        (str(days),),
    )


# ------------------------------------------------------------ signup limit

def signup_attempts(ip: str, window_hours: int) -> int:
    row = db.fetch_one("select count, updated_at from romalume.signup_rate_limits where bucket = %s", (ip,))
    if not row:
        return 0
    age_hours = (_now() - row["updated_at"]).total_seconds() / 3600
    return int(row["count"]) if age_hours < window_hours else 0


def record_signup_attempt(ip: str, window_hours: int) -> int:
    row = db.fetch_one(
        """
        insert into romalume.signup_rate_limits (bucket, count, updated_at)
        values (%s, 1, now())
        on conflict (bucket) do update
          set count = case when romalume.signup_rate_limits.updated_at < now() - (%s || ' hours')::interval
                           then 1 else romalume.signup_rate_limits.count + 1 end,
              updated_at = case when romalume.signup_rate_limits.updated_at < now() - (%s || ' hours')::interval
                                then now() else romalume.signup_rate_limits.updated_at end
        returning count
        """,
        (ip, str(window_hours), str(window_hours)),
    )
    return int(row["count"])


# --------------------------------------------------------------- feedback

def add_feedback(user_id: str | None, body: str, context: dict, client_id: str | None = None) -> dict:
    return _out(db.fetch_one(
        "insert into romalume.feedback (user_id, client_id, body, context) values (%s, %s, %s, %s) returning *",
        (user_id, client_id, body, db.jsonb(context)),
    ))


def list_feedback(limit: int = 500) -> list[dict]:
    return [_out(r) for r in db.fetch_all(
        "select * from romalume.feedback order by created_at desc limit %s", (limit,)
    )]


# ----------------------------------------------------------- stripe events

def claim_stripe_event(event_id: str) -> bool:
    """True if this event is new and now claimed; False if already seen."""
    return db.execute(
        "insert into romalume.stripe_webhook_events (event_id) values (%s) on conflict do nothing", (event_id,)
    ) > 0


def release_stripe_event(event_id: str) -> None:
    db.execute("delete from romalume.stripe_webhook_events where event_id = %s", (event_id,))


# ------------------------------------------------------------ user removal

def delete_user_rows(user_id: str) -> None:
    with db.transaction() as conn:
        for table in ("usage_logs", "feedback", "documents", "conversations", "projects", "user_settings"):
            db.execute(f"delete from romalume.{table} where user_id = %s", (user_id,), conn=conn)
        db.execute("delete from romalume.member_audiences where user_id = %s", (user_id,), conn=conn)
        db.execute("delete from public.admin_users where user_id = %s", (user_id,), conn=conn)
