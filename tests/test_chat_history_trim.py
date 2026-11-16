import os
import unittest

os.environ.setdefault("ROMALUME_SKIP_STARTUP", "1")


class ChatHistoryTrimTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main
        cls.main = main

    def _history(self, n, start="user"):
        roles = ["user", "assistant"] if start == "user" else ["assistant", "user"]
        return [{"role": roles[i % 2], "content": f"m{i}"} for i in range(n)]

    def test_short_history_unchanged(self):
        h = self._history(10)
        self.assertEqual(self.main.trim_chat_history(h), h)

    def test_long_history_trimmed_to_limit(self):
        limit = self.main.MAX_CHAT_HISTORY_MESSAGES
        h = self._history(109)
        out = self.main.trim_chat_history(h)
        self.assertLessEqual(len(out), limit)
        self.assertEqual(out[-1], h[-1])
        self.assertEqual(out[0]["role"], "user")

    def test_earlier_context_kept(self):
        h = [{"role": "context", "content": "doc"}] + self._history(150)
        out = self.main.trim_chat_history(h)
        self.assertEqual(out[0]["role"], "context")
        self.assertLessEqual(len(out), self.main.MAX_CHAT_HISTORY_MESSAGES)
        self.assertEqual(out[-1], h[-1])

    def test_chat_request_accepts_109_messages(self):
        model = next(iter(self.main.ALLOWED_MODEL_IDS))
        req = self.main.ChatRequest(history=self._history(109), model=model)
        self.assertLessEqual(len(req.history), self.main.MAX_CHAT_HISTORY_MESSAGES)
        self.assertEqual(req.history[-1].content, "m108")


if __name__ == "__main__":
    unittest.main()
