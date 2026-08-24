import json
import unittest

from project_context import ProjectContextError, load_project_context


class FakeBlob:
    def __init__(self, value):
        self.value = value

    def download_as_text(self, encoding="utf-8"):
        del encoding
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class FakeBucket:
    def __init__(self, values):
        self.values = values

    def blob(self, path):
        return FakeBlob(self.values[path])


class FakeStore:
    def __init__(self, project, sources):
        self.project = project
        self.sources = sources

    def get_project_record(self, user_id, project_id):
        del user_id, project_id
        return self.project

    def list_sources(self, user_id, project_id):
        del user_id, project_id
        return self.sources


class FakeRag:
    def __init__(self, results):
        self.results = results
        self.call = None

    def search(self, *args, **kwargs):
        self.call = (args, kwargs)
        return self.results


SOURCES = [
    {
        "id": "source-1",
        "source_num": 1,
        "status": "ready",
        "filename": "record.pdf",
        "label": "Record",
        "text_path": "record.txt",
        "pages_path": "record.pages.json",
    },
    {
        "id": "source-2",
        "source_num": 2,
        "status": "processing",
        "filename": "pending.pdf",
    },
]


class ProjectContextTests(unittest.TestCase):
    def test_full_mode_loads_every_ready_source_segment(self):
        project = {
            "id": "project-1",
            "context_mode": "full",
            "draft": {"markdown": "# Draft"},
        }
        bucket = FakeBucket(
            {
                "record.txt": "Page one\nPage two",
                "record.pages.json": json.dumps(
                    [
                        {"page": 1, "start": 0, "end": 8},
                        {"page": 2, "start": 9, "end": 17},
                    ]
                ),
            }
        )

        context = load_project_context(
            store=FakeStore(project, SOURCES),
            bucket=bucket,
            rag=None,
            user_id="user-1",
            project_id="project-1",
            history=[{"role": "user", "content": "Question"}],
        )

        self.assertEqual(context.draft, "# Draft")
        self.assertEqual(len(context.sources), 1)
        self.assertEqual(
            context.sources[0]["segments"],
            [
                {"page": 1, "text": "Page one"},
                {"page": 2, "text": "Page two"},
            ],
        )

    def test_retrieval_mode_filters_by_project_and_uses_top_forty(self):
        project = {"id": "project-1", "context_mode": "retrieval", "draft": {}}
        rag = FakeRag(
            [
                {
                    "source_id": "source-1",
                    "chunk_text": "Relevant excerpt",
                    "page": 3,
                }
            ]
        )

        context = load_project_context(
            store=FakeStore(project, SOURCES),
            bucket=None,
            rag=rag,
            user_id="user-1",
            project_id="project-1",
            history=[{"role": "user", "content": "Limitations question"}],
        )

        args, kwargs = rag.call
        self.assertEqual(args, ("user-1", "Limitations question"))
        self.assertEqual(kwargs["top_k"], 40)
        self.assertEqual(kwargs["project_id"], "project-1")
        self.assertEqual(
            context.sources[0]["segments"],
            [{"text": "Relevant excerpt", "page": 3}],
        )

    def test_retrieval_failure_is_not_silently_treated_as_no_sources(self):
        project = {"id": "project-1", "context_mode": "retrieval", "draft": {}}
        with self.assertRaisesRegex(ProjectContextError, "unavailable"):
            load_project_context(
                store=FakeStore(project, SOURCES),
                bucket=None,
                rag=None,
                user_id="user-1",
                project_id="project-1",
                history=[],
            )


if __name__ == "__main__":
    unittest.main()
