import asyncio
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4


@unittest.skipUnless(
    os.getenv("FIRESTORE_EMULATOR_HOST"),
    "requires the Firestore emulator",
)
class ProjectGenerationFirestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def setUp(self):
        main = self.main
        self.user_id = f"generation-user-{uuid4().hex}"
        main.db.collection("users").document(self.user_id).set(
            {"subscription_status": "active"}
        )
        self.store = main.ProjectStore(main.db)
        self.project = self.store.create_project(
            self.user_id,
            name="Smith memo",
            kind="memo",
            charge={
                "question": "When did Smith learn of the injury?",
                "jurisdiction": "Ohio",
                "audience": "Partner",
                "format_notes": "",
                "free_text": "",
            },
            default_model="claude-sonnet-5",
        )
        source = self.store.reserve_source(
            self.user_id,
            self.project["id"],
            filename="record.pdf",
            content_type="application/pdf",
            size=100,
            label="Record",
        )
        self.source_id = source["id"]
        self.store.finalize_source(
            self.user_id,
            self.project["id"],
            self.source_id,
            {
                "text_path": "record.txt",
                "pages_path": "record.pages.json",
                "storage_path": "record.pdf",
                "pages": 1,
                "map_kind": "page",
                "text_chars": 37,
                "estimated_tokens": 10,
            },
        )

        class FakeBlob:
            def __init__(blob_self, path):
                blob_self.path = path

            def download_as_text(blob_self, encoding="utf-8"):
                del encoding
                if blob_self.path == "record.txt":
                    return "Smith learned of the injury in 2022."
                if blob_self.path == "record.pages.json":
                    return json.dumps([{"page": 1, "start": 0, "end": 40}])
                raise KeyError(blob_self.path)

        class FakeBucket:
            def blob(bucket_self, path):
                del bucket_self
                return FakeBlob(path)

        self.bucket = FakeBucket()

    def tearDown(self):
        self.main.db.recursive_delete(
            self.main.db.collection("users").document(self.user_id)
        )

    def _request(self, model, chat_id):
        return self.main.ChatRequest(
            history=[{"role": "user", "content": "Answer from the record."}],
            model=model,
            project_id=self.project["id"],
            chat_id=chat_id,
            mode="brainstorm",
        )

    @staticmethod
    def _collect(generator):
        async def collect():
            return [event async for event in generator]

        return asyncio.run(collect())

    def _assert_project_result(self, events, chat_id):
        citation_events = [event for event in events if '"citations"' in event]
        self.assertEqual(len(citation_events), 1)
        self.assertLess(events.index(citation_events[0]), events.index("data: [DONE]\n\n"))

        chat = self.store.get_chat(self.user_id, self.project["id"], chat_id)
        assistant = chat["messages"][-1]
        self.assertEqual(assistant["role"], "assistant")
        self.assertEqual(assistant["citations"][0]["source_id"], self.source_id)
        self.assertEqual(assistant["citations"][0]["page"], 1)
        current_chat = (
            self.main.db.collection("users")
            .document(self.user_id)
            .collection("conversations")
            .document("current_chat")
            .get()
        )
        self.assertFalse(current_chat.exists)

    def test_langchain_path_uses_shared_project_prompt_and_saves_citations(self):
        chat = self.store.create_chat(
            self.user_id,
            self.project["id"],
            title="Record question",
            mode="brainstorm",
            model="claude-sonnet-5",
        )

        class FakeLlm:
            def __init__(fake_self):
                fake_self.history = None

            async def astream(fake_self, history):
                fake_self.history = history
                yield SimpleNamespace(content="Smith learned in 2022 [1, p. 1].")

        fake_llm = FakeLlm()
        with (
            patch.object(self.main, "bucket", self.bucket),
            patch.object(self.main, "get_llm", return_value=fake_llm),
            patch.object(self.main, "log_usage_with_cost"),
        ):
            events = self._collect(
                self.main.generate_chat_response(
                    self._request("claude-sonnet-5", chat["id"]),
                    self.user_id,
                )
            )

        system_blocks = fake_llm.history[0]["content"]
        system_text = "\n".join(block["text"] for block in system_blocks)
        self.assertIn("PROJECT CHARGE", system_text)
        self.assertIn("=== [1] Record — page 1 ===", system_text)
        self.assertEqual(system_blocks[1]["cache_control"], {"type": "ephemeral"})
        self._assert_project_result(events, chat["id"])

    def test_gpt5_path_uses_same_project_prompt_and_saves_citations(self):
        chat = self.store.create_chat(
            self.user_id,
            self.project["id"],
            title="GPT record question",
            mode="brainstorm",
            model="gpt-5.6-sol",
        )
        captured = {}

        class FakeResponse:
            def __aiter__(fake_self):
                del fake_self

                async def events():
                    yield SimpleNamespace(
                        type="response.output_text.delta",
                        delta="Smith learned in 2022 [1, p. 1].",
                    )

                return events()

        class FakeResponses:
            async def create(fake_self, **kwargs):
                del fake_self
                captured.update(kwargs)
                return FakeResponse()

        class FakeOpenAI:
            def __init__(fake_self, api_key=None):
                del api_key
                fake_self.responses = FakeResponses()

        with (
            patch.object(self.main, "bucket", self.bucket),
            patch.object(self.main, "AsyncOpenAI", FakeOpenAI),
            patch.object(self.main, "log_usage_with_cost"),
        ):
            events = self._collect(
                self.main.generate_chat_response(
                    self._request("gpt-5.6-sol", chat["id"]),
                    self.user_id,
                )
            )

        system_text = captured["input"][0]["content"]
        self.assertIn("PROJECT CHARGE", system_text)
        self.assertIn("=== [1] Record — page 1 ===", system_text)
        self._assert_project_result(events, chat["id"])


if __name__ == "__main__":
    unittest.main()
