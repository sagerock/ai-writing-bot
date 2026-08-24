import unittest

from rag_identity import stable_point_id


class RAGIdentityTests(unittest.TestCase):
    def test_point_ids_are_deterministic(self):
        first = stable_point_id("user:file.pdf", 3)
        self.assertEqual(first, stable_point_id("user:file.pdf", 3))
        self.assertGreaterEqual(first, 0)
        self.assertLessEqual(first, 0x7FFFFFFFFFFFFFFF)

    def test_point_ids_change_with_document_or_chunk(self):
        base = stable_point_id("user:file.pdf", 3)
        self.assertNotEqual(base, stable_point_id("user:file.pdf", 4))
        self.assertNotEqual(base, stable_point_id("other:file.pdf", 3))


if __name__ == "__main__":
    unittest.main()
