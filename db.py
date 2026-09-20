"""Postgres access for the RomaLume API (Supabase).

One connection pool per process, built from ``DATABASE_URL`` (the Supabase
transaction pooler string). Every query runs in ``romalume``-qualified SQL;
the pool sets ``search_path`` so unqualified names resolve there first.

Helpers return plain dicts. Callers that need atomicity use ``transaction()``.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL") or ""

_pool: ConnectionPool | None = None


def is_configured() -> bool:
    return bool(DATABASE_URL)


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set.")
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=1,
            max_size=int(os.getenv("DB_POOL_MAX", "8")),
            kwargs={
                "row_factory": dict_row,
                "options": "-c search_path=romalume,public",
                "prepare_threshold": None,  # pgbouncer transaction mode
            },
            open=True,
        )
    return _pool


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    with pool().connection() as conn:
        yield conn


@contextmanager
def transaction() -> Iterator[psycopg.Connection]:
    """A connection whose work commits on exit or rolls back on error."""
    with pool().connection() as conn:
        with conn.transaction():
            yield conn


def fetch_one(sql: str, params: Any = None, conn: psycopg.Connection | None = None) -> dict | None:
    if conn is not None:
        return conn.execute(sql, params).fetchone()
    with connection() as c:
        return c.execute(sql, params).fetchone()


def fetch_all(sql: str, params: Any = None, conn: psycopg.Connection | None = None) -> list[dict]:
    if conn is not None:
        return conn.execute(sql, params).fetchall()
    with connection() as c:
        return c.execute(sql, params).fetchall()


def execute(sql: str, params: Any = None, conn: psycopg.Connection | None = None) -> int:
    if conn is not None:
        return conn.execute(sql, params).rowcount
    with connection() as c:
        return c.execute(sql, params).rowcount


def jsonb(value: Any) -> Jsonb:
    """Wrap a Python value for a jsonb parameter."""
    return Jsonb(value)
