import unittest

from ebook_gpt_translator.documents import _format_epub_text, _format_reading_text


class DocumentsTests(unittest.TestCase):
    def test_format_reading_text_inserts_blank_lines_after_sentence_marks(self) -> None:
        text = "第一句。第二句？第三句！第四句：第五句；第六句"
        formatted = _format_reading_text(text)
        self.assertEqual(
            formatted,
            "第一句。\n\n第二句？\n\n第三句！\n\n第四句：\n\n第五句；\n\n第六句",
        )

    def test_format_epub_text_preserves_breaks_as_html(self) -> None:
        text = "第一句。第二句？"
        formatted = _format_epub_text(text)
        self.assertEqual(formatted, "第一句。<br /><br />第二句？")


if __name__ == "__main__":
    unittest.main()
