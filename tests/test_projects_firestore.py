import os
import unittest
from uuid import uuid4

from project_store import ProjectNotFound, ProjectStore


@unittest.skipUnless(
    os.getenv("FIRESTORE_EMULATOR_HOST"),
    "requires the Firestore emulator",
)
class ProjectStoreFirestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from google.cloud import firestore

        cls.db = firestore.Client(project="demo-romalume")

    def setUp(self):
        self.user_id = f"test-user-{uuid4().hex}"
        self.other_user_id = f"other-user-{uuid4().hex}"
        self.store = ProjectStore(self.db, full_context_tokens=10)
        self.project = self.store.create_project(
            self.user_id,
            name="Limitations memo",
            kind="memo",
            charge={
                "question": "Is the claim timely?",
                "jurisdiction": "Ohio",
                "audience": "Partner",
                "format_notes": "Short answer first",
                "free_text": "",
            },
            default_model="claude-sonnet-5",
        )

    def tearDown(self):
        self.db.recursive_delete(
            self.db.collection("users").document(self.user_id)
        )
        self.db.recursive_delete(
            self.db.collection("users").document(self.other_user_id)
        )

    def test_project_crud_is_scoped_to_the_authenticated_owner_path(self):
        projects = self.store.list_projects(self.user_id)
        self.assertEqual([project["id"] for project in projects], [self.project["id"]])
        self.assertEqual(projects[0]["source_count"], 0)
        self.assertEqual(projects[0]["chat_count"], 0)

        with self.assertRaises(ProjectNotFound):
            self.store.get_project(self.other_user_id, self.project["id"])

        updated = self.store.update_project(
            self.user_id,
            self.project["id"],
            {"name": "Updated memo"},
        )
        self.assertEqual(updated["name"], "Updated memo")

        self.store.archive_project(self.user_id, self.project["id"])
        self.assertEqual(self.store.list_projects(self.user_id), [])
        self.assertEqual(
            len(self.store.list_projects(self.user_id, include_archived=True)),
            1,
        )

    def test_source_numbers_are_never_reused_and_context_mode_recomputes(self):
        first = self.store.reserve_source(
            self.user_id,
            self.project["id"],
            filename="first.pdf",
            content_type="application/pdf",
            size=100,
            label="First",
        )
        self.store.finalize_source(
            self.user_id,
            self.project["id"],
            first["id"],
            {"estimated_tokens": 9, "text_chars": 36},
        )
        self.assertEqual(first["source_num"], 1)
        self.assertEqual(
            self.store.get_project(self.user_id, self.project["id"])["context_mode"],
            "full",
        )

        second = self.store.reserve_source(
            self.user_id,
            self.project["id"],
            filename="second.txt",
            content_type="text/plain",
            size=50,
            label="Second",
        )
        self.store.finalize_source(
            self.user_id,
            self.project["id"],
            second["id"],
            {"estimated_tokens": 2, "text_chars": 8},
        )
        self.assertEqual(
            self.store.get_project(self.user_id, self.project["id"])["context_mode"],
            "retrieval",
        )

        self.store.delete_source(self.user_id, self.project["id"], second["id"])
        third = self.store.reserve_source(
            self.user_id,
            self.project["id"],
            filename="third.md",
            content_type="text/markdown",
            size=20,
            label="Third",
        )
        self.assertEqual(third["source_num"], 3)
        self.assertEqual(
            self.store.get_project(self.user_id, self.project["id"])["context_mode"],
            "full",
        )

    def test_drafts_version_restore_and_keep_only_fifty_snapshots(self):
        first = self.store.save_draft(
            self.user_id,
            self.project["id"],
            markdown="First draft",
            reason="initial",
        )
        second = self.store.save_draft(
            self.user_id,
            self.project["id"],
            markdown="Second draft",
            reason="revision",
        )
        self.assertEqual((first["version"], second["version"]), (1, 2))

        restored = self.store.restore_draft(
            self.user_id,
            self.project["id"],
            version=1,
        )
        self.assertEqual(restored["markdown"], "First draft")
        self.assertEqual(restored["version"], 3)

        for version in range(4, 53):
            self.store.save_draft(
                self.user_id,
                self.project["id"],
                markdown=f"Draft {version}",
                reason="cap test",
            )
        versions = self.store.list_draft_versions(self.user_id, self.project["id"])
        self.assertEqual(len(versions), 50)
        self.assertEqual(versions[0]["version"], 52)
        self.assertEqual(versions[-1]["version"], 3)

    def test_chat_create_get_and_delete(self):
        chat = self.store.create_chat(
            self.user_id,
            self.project["id"],
            title="Analyze Smith",
            mode="brainstorm",
            model=None,
        )
        loaded = self.store.get_chat(
            self.user_id,
            self.project["id"],
            chat["id"],
        )
        self.assertEqual(loaded["model"], "claude-sonnet-5")
        self.assertEqual(loaded["messages"], [])

        saved = self.store.save_chat(
            self.user_id,
            self.project["id"],
            chat["id"],
            messages=(
                {"role": role, "content": content}
                for role, content in (("user", "Question"), ("assistant", "Answer"))
            ),
            mode="brainstorm",
            model="claude-sonnet-5",
        )
        self.assertEqual(saved["message_count"], 2)
        detail = self.store.get_project(self.user_id, self.project["id"])
        self.assertEqual(detail["chats"][0]["message_count"], 2)
        self.assertNotIn("messages", detail["chats"][0])

        self.store.delete_chat(self.user_id, self.project["id"], chat["id"])
        detail = self.store.get_project(self.user_id, self.project["id"])
        self.assertEqual(detail["chats"], [])


@unittest.skipUnless(
    os.getenv("FIRESTORE_EMULATOR_HOST"),
    "requires the Firestore emulator",
)
class ProjectRoutesFirestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi import FastAPI, Header, HTTPException
        from fastapi.testclient import TestClient
        from google.cloud import firestore

        from projects import create_projects_router

        class FakeBlob:
            def __init__(self, objects, path):
                self.objects = objects
                self.path = path

            def upload_from_string(self, data, content_type=None):
                del content_type
                self.objects[self.path] = data if isinstance(data, bytes) else data.encode()

            def download_as_text(self, encoding="utf-8"):
                return self.objects[self.path].decode(encoding)

            def exists(self):
                return self.path in self.objects

            def delete(self):
                self.objects.pop(self.path, None)

        class FakeBucket:
            def __init__(self):
                self.objects = {}

            def blob(self, path):
                return FakeBlob(self.objects, path)

        class FakeRag:
            def __init__(self):
                self.indexed = []
                self.deleted = []

            def index_document(self, *args, **kwargs):
                self.indexed.append((args, kwargs))
                return 1

            def delete_document(self, *args, **kwargs):
                self.deleted.append((args, kwargs))

        async def current_user(authorization: str | None = Header(default=None)):
            if authorization != "Bearer test-user":
                raise HTTPException(status_code=401, detail="Unauthorized")
            return {"user_id": "route-test-user"}

        cls.db = firestore.Client(project="demo-romalume")
        cls.bucket = FakeBucket()
        cls.rag = FakeRag()
        app = FastAPI()
        app.include_router(
            create_projects_router(
                db=cls.db,
                get_current_user=current_user,
                get_storage_bucket=lambda: cls.bucket,
                get_rag_service=lambda: cls.rag,
                safe_filename=lambda filename: filename.rsplit("/", 1)[-1],
                estimate_tokens=lambda text: max(1, len(text) // 4),
                allowed_model_ids={"claude-sonnet-5", "claude-opus-5"},
                max_upload_bytes=1_000_000,
                max_pdf_pages=20,
                full_context_tokens=100,
            )
        )
        cls.client = TestClient(app)
        cls.headers = {"Authorization": "Bearer test-user"}

    def setUp(self):
        self.db.recursive_delete(
            self.db.collection("users").document("route-test-user")
        )
        self.bucket.objects.clear()
        self.rag.indexed.clear()
        self.rag.deleted.clear()

    def tearDown(self):
        self.db.recursive_delete(
            self.db.collection("users").document("route-test-user")
        )

    def test_complete_project_endpoint_lifecycle(self):
        self.assertEqual(self.client.get("/projects").status_code, 401)

        response = self.client.post(
            "/projects",
            headers=self.headers,
            json={
                "name": "Smith memo",
                "kind": "memo",
                "charge": {"question": "Is Smith's claim timely?"},
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        project_id = response.json()["id"]
        self.assertEqual(response.json()["default_model"], "claude-sonnet-5")

        response = self.client.get("/projects", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()[0]["id"], project_id)

        response = self.client.patch(
            f"/projects/{project_id}",
            headers=self.headers,
            json={"name": "Smith limitations memo", "default_model": "claude-opus-5"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["default_model"], "claude-opus-5")

        response = self.client.post(
            f"/projects/{project_id}/sources",
            headers=self.headers,
            files={"file": ("record.txt", b"First paragraph.\n\nSecond paragraph.", "text/plain")},
            data={"label": "The Record"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        source_id = response.json()["source"]["id"]
        self.assertEqual(response.json()["source"]["source_num"], 1)
        self.assertTrue(response.json()["source"]["indexed"])
        self.assertEqual(len(self.rag.indexed), 1)

        response = self.client.patch(
            f"/projects/{project_id}/sources/{source_id}",
            headers=self.headers,
            json={"label": "Smith Record"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["label"], "Smith Record")

        response = self.client.get(
            f"/projects/{project_id}/sources/{source_id}/text?page=1",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["text"], "First paragraph.")

        response = self.client.put(
            f"/projects/{project_id}/draft",
            headers=self.headers,
            json={"markdown": "# Analysis\n\nInitial analysis.", "reason": "manual"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["version"], 1)
        versions = self.client.get(
            f"/projects/{project_id}/draft/versions",
            headers=self.headers,
        )
        self.assertEqual(versions.status_code, 200, versions.text)
        self.assertEqual(versions.json()[0]["version"], 1)
        restored = self.client.post(
            f"/projects/{project_id}/draft/restore",
            headers=self.headers,
            json={"version": 1},
        )
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()["version"], 2)

        response = self.client.post(
            f"/projects/{project_id}/chats",
            headers=self.headers,
            json={"title": "Issue spotting", "mode": "brainstorm"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        chat_id = response.json()["id"]
        chat = self.client.get(
            f"/projects/{project_id}/chats/{chat_id}",
            headers=self.headers,
        )
        self.assertEqual(chat.status_code, 200, chat.text)
        self.assertEqual(chat.json()["title"], "Issue spotting")
        self.assertEqual(
            self.client.delete(
                f"/projects/{project_id}/chats/{chat_id}", headers=self.headers
            ).status_code,
            200,
        )

        detail = self.client.get(f"/projects/{project_id}", headers=self.headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["sources"][0]["id"], source_id)

        response = self.client.delete(
            f"/projects/{project_id}/sources/{source_id}",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.rag.deleted), 1)

        response = self.client.delete(
            f"/projects/{project_id}", headers=self.headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            self.client.get("/projects", headers=self.headers).json(),
            [],
        )

    def test_template_catalog_and_research_project_scaffold(self):
        templates = self.client.get("/projects/templates", headers=self.headers)
        self.assertEqual(templates.status_code, 200, templates.text)
        self.assertEqual(
            [template["id"] for template in templates.json()],
            ["memo", "research_paper", "article", "blog_post", "general_document"],
        )

        response = self.client.post(
            "/projects",
            headers=self.headers,
            json={
                "name": "Institutional change",
                "kind": "research_paper",
                "charge": {
                    "research_question": "Why do institutions change?",
                    "citation_style": "Chicago",
                },
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["kind"], "research_paper")
        self.assertIn("## Background and Literature Review", response.json()["draft"]["markdown"])

        invalid = self.client.post(
            "/projects",
            headers=self.headers,
            json={
                "name": "Invalid research",
                "kind": "research_paper",
                "charge": {"question": "Wrong field"},
            },
        )
        self.assertEqual(invalid.status_code, 422, invalid.text)


if __name__ == "__main__":
    unittest.main()
