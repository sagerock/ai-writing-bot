import unittest

from rag_chunks import split_source_chunks


class RagChunksTests(unittest.TestCase):
    def test_project_chunks_never_cross_page_boundaries(self):
        text = "page one text\npage two text"
        chunks = split_source_chunks(
            text,
            lambda value: [value],
            [
                {"page": 1, "start": 0, "end": 13},
                {"page": 2, "start": 14, "end": 27},
            ],
        )

        self.assertEqual(
            chunks,
            [
                ("page one text", {"page": 1}),
                ("page two text", {"page": 2}),
            ],
        )

    def test_legacy_chunks_have_no_project_location(self):
        chunks = split_source_chunks("abcdef", lambda value: [value[:3], value[3:]])
        self.assertEqual(chunks, [("abc", {}), ("def", {})])


if __name__ == "__main__":
    unittest.main()
