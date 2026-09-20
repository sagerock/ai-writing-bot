"""Throwaway auth users for Postgres-backed tests.

Tests that touch the database run only when ``DATABASE_URL`` is set. They
create users directly in ``auth.users`` with a recognisable email domain and
remove them (and every romalume row keyed to them) afterwards.
"""

from __future__ import annotations

import os
from uuid import uuid4

POSTGRES_AVAILABLE = bool(os.getenv("DATABASE_URL"))
TEST_EMAIL_DOMAIN = "romalume-tests.invalid"


class PostgresFixture:
    def __init__(self):
        import db

        self.db = db
        self.user_ids: list[str] = []

    def create_user(self, *, email: str | None = None) -> str:
        user_id = str(uuid4())
        email = email or f"{user_id}@{TEST_EMAIL_DOMAIN}"
        self.db.execute("select romalume.test_create_auth_user(%s, %s)", (user_id, email))
        self.user_ids.append(user_id)
        return user_id

    def cleanup(self) -> None:
        import user_store

        for user_id in self.user_ids:
            try:
                user_store.delete_user_rows(user_id)
            finally:
                self.db.execute("select romalume.test_delete_auth_user(%s)", (user_id,))
        self.user_ids = []
