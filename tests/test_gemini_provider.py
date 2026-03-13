import unittest
from unittest.mock import patch
import json

from ebook_gpt_translator.config import ProviderConfig, TranslationConfig
from ebook_gpt_translator.providers import GeminiCLIProvider


class GeminiProviderTests(unittest.TestCase):
    @patch("ebook_gpt_translator.providers.shutil.which", return_value="/usr/bin/gemini")
    @patch("ebook_gpt_translator.providers.subprocess.run")
    def test_translate_uses_gemini_cli(self, mock_run, _mock_which) -> None:
        class Result:
            returncode = 0
            stdout = json.dumps({"translation": "Hallo Welt"})
            stderr = ""

        mock_run.return_value = Result()

        provider = GeminiCLIProvider(
            ProviderConfig(kind="gemini", model="gemini-2.5-pro"),
            TranslationConfig(),
        )
        result = provider.translate("Hello world", "System prompt")

        self.assertEqual(result.text, "Hallo Welt")
        cmd = mock_run.call_args[0][0]
        self.assertIn("-m", cmd)
        self.assertIn("gemini-2.5-pro", cmd)
        # Verify prompt was passed via stdin
        self.assertIn("System prompt", mock_run.call_args[1]["input"])

    @patch("ebook_gpt_translator.providers.shutil.which", return_value="/usr/bin/gemini")
    @patch("ebook_gpt_translator.providers.subprocess.run")
    def test_extract_plain_text_fallback(self, mock_run, _mock_which) -> None:
        """When Gemini returns plain text instead of JSON."""

        class Result:
            returncode = 0
            stdout = "Hallo Welt"
            stderr = ""

        mock_run.return_value = Result()

        provider = GeminiCLIProvider(
            ProviderConfig(kind="gemini", model="gemini-2.5-flash"),
            TranslationConfig(),
        )
        result = provider.translate("Hello world", "System prompt")
        self.assertEqual(result.text, "Hallo Welt")

    @patch("ebook_gpt_translator.providers.shutil.which", return_value="/usr/bin/gemini")
    @patch("ebook_gpt_translator.providers.subprocess.run")
    def test_strips_markdown_fences(self, mock_run, _mock_which) -> None:
        class Result:
            returncode = 0
            stdout = '```json\n{"translation": "Bonjour"}\n```'
            stderr = ""

        mock_run.return_value = Result()

        provider = GeminiCLIProvider(
            ProviderConfig(kind="gemini", model="gemini-2.5-pro"),
            TranslationConfig(),
        )
        result = provider.translate("Hello", "Translate")
        self.assertEqual(result.text, "Bonjour")

    @patch("ebook_gpt_translator.providers.shutil.which", return_value=None)
    def test_raises_if_gemini_not_found(self, _mock_which) -> None:
        with self.assertRaises(RuntimeError):
            GeminiCLIProvider(
                ProviderConfig(kind="gemini", model="gemini-2.5-pro"),
                TranslationConfig(),
            )

    @patch("ebook_gpt_translator.providers.shutil.which", return_value="/usr/bin/gemini")
    @patch("ebook_gpt_translator.providers.subprocess.run")
    def test_retries_on_empty_output(self, mock_run, _mock_which) -> None:
        calls = {"count": 0}

        def fake_run(cmd, input, text, capture_output, check, timeout):
            calls["count"] += 1

            class Result:
                returncode = 0
                stderr = ""

            r = Result()
            if calls["count"] == 1:
                r.stdout = ""
            else:
                r.stdout = json.dumps({"translation": "Bonjour"})
            return r

        mock_run.side_effect = fake_run

        provider = GeminiCLIProvider(
            ProviderConfig(kind="gemini", model="gemini-2.5-pro"),
            TranslationConfig(),
        )
        result = provider.translate("Hello", "Translate")
        self.assertEqual(result.text, "Bonjour")
        self.assertEqual(calls["count"], 2)


if __name__ == "__main__":
    unittest.main()
