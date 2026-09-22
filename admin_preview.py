"""Admin-only client and audience preview tokens.

The preview changes the school library/branding context while deliberately
keeping the administrator's own user id. That makes it useful for verifying
what a client can retrieve without exposing a member's private drafts or chat
history.
"""

from __future__ import annotations

import os
from typing import Iterable

from fastapi import HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


ADMIN_EMAIL = (os.getenv("ROMALUME_ADMIN_EMAIL") or "sage@sagerock.com").strip().lower()
VIEW_TOKEN_MAX_AGE = 12 * 60 * 60
VIEW_TOKEN_SEPARATOR = "::romalume-view::"
AUDIENCES = ("staff", "marketing", "leadership", "board", "finance")

ACCESS_PROFILES = (
    {
        "id": "staff",
        "label": "Staff",
        "description": "General staff library only",
        "audiences": ["staff"],
    },
    {
        "id": "marketing",
        "label": "Marketing",
        "description": "Staff and marketing content",
        "audiences": ["staff", "marketing"],
    },
    {
        "id": "leadership",
        "label": "Leadership",
        "description": "Staff and leadership content",
        "audiences": ["staff", "leadership"],
    },
    {
        "id": "board",
        "label": "Board",
        "description": "Staff and board content",
        "audiences": ["staff", "board"],
    },
    {
        "id": "finance",
        "label": "Finance",
        "description": "Staff and financial content",
        "audiences": ["staff", "finance"],
    },
    {
        "id": "full",
        "label": "Full access",
        "description": "Every audience",
        "audiences": list(AUDIENCES),
    },
)


def is_romalume_admin(user: dict) -> bool:
    """RomaLume intentionally has one administrator for now."""
    return bool(
        user.get("is_super_admin")
        and (user.get("email") or "").strip().lower() == ADMIN_EMAIL
    )


def _secret() -> str:
    # SUPABASE_SERVICE_KEY already exists in every deployed API environment and
    # never leaves the server. ADMIN_VIEW_SECRET permits independent rotation.
    secret = os.getenv("ADMIN_VIEW_SECRET") or os.getenv("SUPABASE_SERVICE_KEY")
    if not secret:
        raise HTTPException(status_code=503, detail="Admin preview is not configured.")
    return secret


def normalize_audiences(audiences: Iterable[str]) -> list[str]:
    selected = set(audiences)
    if not selected or not selected.issubset(AUDIENCES):
        raise HTTPException(status_code=422, detail="Invalid audience selection.")
    # All client members receive staff access in the underlying permission model.
    selected.add("staff")
    return [audience for audience in AUDIENCES if audience in selected]


def create_view_token(*, actor: dict, client_id: str, audiences: Iterable[str]) -> str:
    if not is_romalume_admin(actor):
        raise HTTPException(status_code=403, detail="Admin preview is restricted.")
    payload = {
        "actor_id": actor["user_id"],
        "actor_email": ADMIN_EMAIL,
        "client_id": client_id,
        "audiences": normalize_audiences(audiences),
    }
    return URLSafeTimedSerializer(_secret(), salt="romalume-admin-preview").dumps(payload)


def verify_view_token(token: str, *, actor: dict) -> dict:
    if not is_romalume_admin(actor):
        raise HTTPException(status_code=403, detail="Admin preview is restricted.")
    try:
        payload = URLSafeTimedSerializer(_secret(), salt="romalume-admin-preview").loads(
            token,
            max_age=VIEW_TOKEN_MAX_AGE,
        )
        if payload.get("actor_id") != actor.get("user_id"):
            raise KeyError("actor_id")
        if (payload.get("actor_email") or "").lower() != ADMIN_EMAIL:
            raise KeyError("actor_email")
        payload["audiences"] = normalize_audiences(payload.get("audiences") or [])
        if not payload.get("client_id"):
            raise KeyError("client_id")
        return payload
    except SignatureExpired as error:
        raise HTTPException(status_code=401, detail="Admin preview has expired.") from error
    except (BadSignature, KeyError, TypeError) as error:
        raise HTTPException(status_code=401, detail="Invalid admin preview.") from error


def split_bearer_token(raw_token: str) -> tuple[str, str | None]:
    access_token, separator, view_token = raw_token.partition(VIEW_TOKEN_SEPARATOR)
    return access_token, view_token if separator and view_token else None
