"""Supabase Storage with the small surface the app used from Cloud Storage.

``bucket.blob(path)`` returns an object with ``upload_from_string``,
``download_as_bytes``, ``download_as_text``, ``exists`` and ``delete`` so the
upload and context-loading code did not have to change shape when Firebase
Storage was retired (2026-09-20).

Environment:
    SUPABASE_URL, SUPABASE_SERVICE_KEY, STORAGE_BUCKET (default romalume-sources)
"""

from __future__ import annotations

import os
from urllib.parse import quote

import httpx

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or ""
DEFAULT_BUCKET = os.getenv("STORAGE_BUCKET") or "romalume-sources"

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class BlobNotFound(FileNotFoundError):
    pass


def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


def _headers(extra: dict | None = None) -> dict:
    h = {"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}
    if extra:
        h.update(extra)
    return h


class Blob:
    def __init__(self, bucket: str, path: str):
        self.bucket = bucket
        self.name = path
        self._url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{quote(path, safe='/')}"

    def upload_from_string(self, data: bytes | str, content_type: str | None = None) -> None:
        if isinstance(data, str):
            data = data.encode("utf-8")
        headers = _headers({"x-upsert": "true", "Content-Type": content_type or "application/octet-stream"})
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(self._url, headers=headers, content=data)
        if response.status_code >= 400:
            raise RuntimeError(f"Storage upload failed ({response.status_code}): {response.text[:200]}")

    def download_as_bytes(self) -> bytes:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.get(self._url, headers=_headers())
        if response.status_code == 404 or response.status_code == 400:
            raise BlobNotFound(self.name)
        if response.status_code >= 400:
            raise RuntimeError(f"Storage download failed ({response.status_code}): {response.text[:200]}")
        return response.content

    def download_as_text(self, encoding: str = "utf-8") -> str:
        return self.download_as_bytes().decode(encoding)

    def exists(self) -> bool:
        info_url = f"{SUPABASE_URL}/storage/v1/object/info/{self.bucket}/{quote(self.name, safe='/')}"
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.get(info_url, headers=_headers())
        return response.status_code == 200

    def signed_url(self, expires_in: int = 3600, download_name: str | None = None) -> str:
        sign_url = f"{SUPABASE_URL}/storage/v1/object/sign/{self.bucket}/{quote(self.name, safe='/')}"
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(
                sign_url,
                headers=_headers({"Content-Type": "application/json"}),
                json={"expiresIn": expires_in},
            )
        if response.status_code >= 400:
            raise RuntimeError(f"Storage sign failed ({response.status_code}): {response.text[:200]}")
        signed = response.json().get("signedURL") or ""
        url = f"{SUPABASE_URL}/storage/v1{signed}"
        if download_name:
            url += ("&" if "?" in url else "?") + "download=" + quote(download_name)
        return url

    def delete(self) -> None:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.delete(self._url, headers=_headers())
        if response.status_code >= 400 and response.status_code != 404:
            raise RuntimeError(f"Storage delete failed ({response.status_code}): {response.text[:200]}")


class Bucket:
    def __init__(self, name: str = DEFAULT_BUCKET):
        self.name = name

    def blob(self, path: str) -> Blob:
        return Blob(self.name, path)

    def delete_prefix(self, prefix: str) -> int:
        """Delete every object under a prefix (used when a user is removed)."""
        list_url = f"{SUPABASE_URL}/storage/v1/object/list/{self.name}"
        removed = 0
        with httpx.Client(timeout=_TIMEOUT) as client:
            offset = 0
            while True:
                response = client.post(
                    list_url,
                    headers=_headers({"Content-Type": "application/json"}),
                    json={"prefix": prefix, "limit": 100, "offset": offset},
                )
                if response.status_code >= 400:
                    break
                items = response.json() or []
                names = [f"{prefix.rstrip('/')}/{item['name']}" for item in items if item.get("name")]
                if not names:
                    break
                client.request(
                    "DELETE",
                    f"{SUPABASE_URL}/storage/v1/object/{self.name}",
                    headers=_headers({"Content-Type": "application/json"}),
                    json={"prefixes": names},
                )
                removed += len(names)
                if len(items) < 100:
                    break
                offset += 100
        return removed


_bucket: Bucket | None = None


def bucket() -> Bucket:
    global _bucket
    if _bucket is None:
        _bucket = Bucket()
    return _bucket
