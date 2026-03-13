import unittest

from ebook_gpt_translator.providers import (
    _clean_json_artifacts,
    _parse_json_payload,
    _regex_extract_translation,
)


class JsonExtractionTests(unittest.TestCase):
    def test_parse_normal_json(self) -> None:
        parsed = _parse_json_payload('{"translation": "hello world"}')
        self.assertEqual(parsed["translation"], "hello world")

    def test_parse_json_with_markdown_prefix(self) -> None:
        text = 'Here is the result:\n{"translation": "hello"}'
        parsed = _parse_json_payload(text)
        self.assertEqual(parsed["translation"], "hello")

    def test_regex_extracts_from_malformed_json(self) -> None:
        # Unescaped braces in value break json.loads but regex still works
        text = '{"translation": "he looked at the data"}'
        result = _regex_extract_translation(text)
        self.assertEqual(result, "he looked at the data")

    def test_regex_extracts_with_escaped_quotes(self) -> None:
        text = r'{"translation": "he said \"hello\" and left"}'
        result = _regex_extract_translation(text)
        self.assertEqual(result, 'he said "hello" and left')

    def test_regex_extracts_multiline(self) -> None:
        text = '{"translation": "line one\\nline two"}'
        result = _regex_extract_translation(text)
        self.assertEqual(result, "line one\nline two")

    def test_clean_full_json_wrapper(self) -> None:
        text = '{"translation": "clean text"}'
        result = _clean_json_artifacts(text)
        self.assertEqual(result, "clean text")

    def test_clean_trailing_brace(self) -> None:
        text = 'translated text"\n}'
        result = _clean_json_artifacts(text)
        self.assertNotIn("}", result)
        self.assertIn("translated text", result)

    def test_clean_leading_json_key(self) -> None:
        text = '{"translation": "translated text continues here'
        result = _clean_json_artifacts(text)
        self.assertNotIn('"translation"', result)
        self.assertIn("translated text", result)

    def test_clean_preserves_normal_text(self) -> None:
        text = "This is a normal translation without JSON artifacts."
        result = _clean_json_artifacts(text)
        self.assertEqual(result, text)

    def test_regex_returns_empty_for_no_match(self) -> None:
        result = _regex_extract_translation("just plain text")
        self.assertEqual(result, "")

    def test_parse_returns_none_for_garbage(self) -> None:
        result = _parse_json_payload("not json at all")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
