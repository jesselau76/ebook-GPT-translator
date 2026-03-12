import tempfile
import unittest
from pathlib import Path

from ebook_gpt_translator.glossary import Glossary


class GlossaryTests(unittest.TestCase):
    def test_apply_case_insensitive_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "glossary.csv"
            path.write_text("OpenAI,OpenAI\nchapter,章节\n", encoding="utf-8")
            glossary = Glossary.from_path(str(path), case_sensitive=False)
        translated = glossary.apply("This chapter uses OpenAI.")
        self.assertEqual(translated, "This 章节 uses OpenAI.")


if __name__ == "__main__":
    unittest.main()

