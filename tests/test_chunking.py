import unittest

from ebook_gpt_translator.chunking import split_text


class ChunkingTests(unittest.TestCase):
    def test_split_text_respects_limits(self) -> None:
        text = (
            "Sentence one. Sentence two. Sentence three. Sentence four. "
            "Sentence five. Sentence six."
        )
        chunks = split_text(text, max_chars=30, max_tokens=100)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 30 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()

