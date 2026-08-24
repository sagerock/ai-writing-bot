import unittest
from llm_content import stream_chunk_text


class StreamChunkTextTests(unittest.TestCase):
    def test_string_passthrough(self):
        self.assertEqual(stream_chunk_text("hi"), "hi")

    def test_text_blocks_concatenate_without_separator(self):
        blocks = [{"type": "text", "text": "Hel"}, {"type": "text", "text": "lo"}]
        self.assertEqual(stream_chunk_text(blocks), "Hello")

    def test_non_text_blocks_ignored(self):
        blocks = [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "x"}]
        self.assertEqual(stream_chunk_text(blocks), "x")

    def test_untyped_block_and_none(self):
        self.assertEqual(stream_chunk_text([{"text": "a"}, "b"]), "ab")
        self.assertEqual(stream_chunk_text(None), "")


if __name__ == "__main__":
    unittest.main()
