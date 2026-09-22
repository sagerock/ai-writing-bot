import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import admin_preview


class AdminPreviewTests(unittest.TestCase):
    def setUp(self):
        self.admin = {
            "user_id": "11111111-1111-1111-1111-111111111111",
            "email": "sage@sagerock.com",
            "is_super_admin": True,
        }

    def test_only_configured_email_is_admin(self):
        self.assertTrue(admin_preview.is_romalume_admin(self.admin))
        self.assertFalse(admin_preview.is_romalume_admin({**self.admin, "email": "other@example.com"}))
        self.assertFalse(admin_preview.is_romalume_admin({**self.admin, "is_super_admin": False}))

    def test_signed_preview_round_trip_and_staff_is_implicit(self):
        with patch.dict(os.environ, {"ADMIN_VIEW_SECRET": "test-secret"}):
            token = admin_preview.create_view_token(
                actor=self.admin,
                client_id="22222222-2222-2222-2222-222222222222",
                audiences=["finance"],
            )
            payload = admin_preview.verify_view_token(token, actor=self.admin)
        self.assertEqual(payload["audiences"], ["staff", "finance"])
        self.assertEqual(payload["client_id"], "22222222-2222-2222-2222-222222222222")

    def test_preview_cannot_be_used_by_another_actor(self):
        with patch.dict(os.environ, {"ADMIN_VIEW_SECRET": "test-secret"}):
            token = admin_preview.create_view_token(
                actor=self.admin,
                client_id="22222222-2222-2222-2222-222222222222",
                audiences=["marketing"],
            )
            with self.assertRaises(HTTPException):
                admin_preview.verify_view_token(
                    token,
                    actor={**self.admin, "user_id": "33333333-3333-3333-3333-333333333333"},
                )

    def test_unknown_audience_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            admin_preview.normalize_audiences(["staff", "secret"])
        self.assertEqual(raised.exception.status_code, 422)

    def test_bearer_token_split_is_unambiguous(self):
        raw = f"supabase.jwt{admin_preview.VIEW_TOKEN_SEPARATOR}signed-preview"
        self.assertEqual(
            admin_preview.split_bearer_token(raw),
            ("supabase.jwt", "signed-preview"),
        )


if __name__ == "__main__":
    unittest.main()
