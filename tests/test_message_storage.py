import unittest

from message_storage import (
    MAX_STORED_MESSAGES,
    MAX_STORED_MESSAGE_CHARS,
    compact_messages_for_storage,
)


class MessageStorageTests(unittest.TestCase):
    def test_internal_roles_are_not_persisted(self):
        messages = [
            {"role": "system", "content": "private prompt"},
            {"role": "user", "content": "hello"},
        ]

        self.assertEqual(
            compact_messages_for_storage(messages),
            [{"role": "user", "content": "hello"}],
        )

    def test_embedded_image_bytes_are_removed(self):
        messages = [{"role": "user", "content": "photo data:image/png;base64,YWJjZA=="}]

        result = compact_messages_for_storage(messages)

        self.assertNotIn("YWJjZA==", result[0]["content"])
        self.assertIn("Image omitted", result[0]["content"])

    def test_history_and_content_are_bounded(self):
        messages = [
            {"role": "user", "content": "x" * (MAX_STORED_MESSAGE_CHARS + 10)}
            for _ in range(MAX_STORED_MESSAGES + 10)
        ]

        result = compact_messages_for_storage(messages)

        self.assertEqual(len(result), MAX_STORED_MESSAGES)
        self.assertEqual(len(result[0]["content"]), MAX_STORED_MESSAGE_CHARS)


if __name__ == "__main__":
    unittest.main()
