"""RomaLume must never write public.admin_users (the email tool's role table).

No database access: SQL is captured from patched db helpers or read from source.
"""

import re
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import user_store

REPO = Path(__file__).resolve().parent.parent
WRITE_SQL = re.compile(
    r"\b(insert\s+into|update|delete\s+from|truncate)\s+(table\s+)?(public\.)?admin_users\b",
    re.IGNORECASE,
)


class AdminUsersReadOnlyTests(unittest.TestCase):
    def test_delete_user_rows_leaves_admin_users_to_the_cascade(self):
        statements = []

        @contextmanager
        def fake_transaction():
            yield object()

        def fake_execute(sql, params=None, conn=None):
            statements.append(sql)
            return 0

        with patch.object(user_store.db, "transaction", fake_transaction), \
                patch.object(user_store.db, "execute", fake_execute):
            user_store.delete_user_rows("11111111-1111-1111-1111-111111111111")

        self.assertTrue(statements)
        self.assertFalse([s for s in statements if "admin_users" in s])
        self.assertTrue(any("romalume.user_settings" in s for s in statements))

    def test_no_super_admin_toggle(self):
        self.assertFalse(hasattr(user_store, "set_super_admin"))

    def test_no_python_source_writes_admin_users(self):
        offenders = []
        for path in REPO.glob("*.py"):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if WRITE_SQL.search(line):
                    offenders.append(f"{path.name}:{number}: {line.strip()}")
        self.assertEqual(offenders, [])

    def test_role_endpoint_removed(self):
        source = (REPO / "main.py").read_text(encoding="utf-8")
        self.assertNotIn('"/admin/users/{user_id}/role"', source)

    def test_migration_makes_admin_users_select_only(self):
        sql = (REPO / "supabase/migrations/013_admin_users_read_only.sql").read_text(encoding="utf-8")
        body = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        self.assertRegex(body, r"revoke insert, update, delete[^;]*on public\.admin_users from romalume_app")
        self.assertIn("drop policy if exists romalume_app_admin_users on public.admin_users", body)
        self.assertRegex(body, r"create policy romalume_app_admin_users_read on public\.admin_users\s+for select to romalume_app")
        self.assertNotRegex(body, r"grant (insert|update|delete)")


if __name__ == "__main__":
    unittest.main()
