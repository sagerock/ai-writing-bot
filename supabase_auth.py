"""Supabase authentication for the RomaLume API.

When ``AUTH_PROVIDER=supabase`` the API validates the caller's Supabase access
token against the shared SageRock project and resolves which school (client)
they belong to through ``public.admin_users``. This mirrors what the email
tool's Express API does with ``supabase.auth.getUser(token)``.

The returned dict keeps the keys ``main.py`` already reads from a Firebase
token (``user_id``, ``email``) and adds ``client_id``, ``role`` and
``is_super_admin`` so callers can scope school data.

Environment:
    SUPABASE_URL          https://<ref>.supabase.co
    SUPABASE_ANON_KEY     public key, sent as ``apikey`` on the user lookup
    SUPABASE_SERVICE_KEY  service role key, used for the admin_users lookup
"""

from __future__ import annotations

import os
import time

import httpx
from fastapi import HTTPException

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or ""
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or ""

_MEMBERSHIP_TTL_SECONDS = 60
_membership_cache: dict[str, tuple[float, dict]] = {}


def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY and SUPABASE_SERVICE_KEY)


async def _get_user(token: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"},
        )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")
    return response.json()


async def _get_membership(user_id: str) -> dict:
    cached = _membership_cache.get(user_id)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/admin_users",
            params={"select": "role,client_id", "user_id": f"eq.{user_id}", "limit": "1"},
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            },
        )
    rows = response.json() if response.status_code == 200 else []
    row = rows[0] if rows else {}
    membership = {
        "role": row.get("role"),
        "client_id": row.get("client_id"),
        "is_super_admin": row.get("role") == "super_admin",
    }
    _membership_cache[user_id] = (time.monotonic() + _MEMBERSHIP_TTL_SECONDS, membership)
    return membership


async def verify_supabase_token(token: str) -> dict:
    """Validate a Supabase access token and return the RomaLume user record."""
    if not is_configured():
        raise HTTPException(status_code=500, detail="Supabase authentication is not configured.")
    user = await _get_user(token)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")
    membership = await _get_membership(user_id)
    return {
        "user_id": user_id,
        "uid": user_id,
        "email": user.get("email"),
        "email_verified": bool(user.get("email_confirmed_at")),
        "auth_provider": "supabase",
        **membership,
    }
