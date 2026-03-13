import unittest
from unittest.mock import patch
import json

from ebook_gpt_translator.config import ProviderConfig, TranslationConfig
from ebook_gpt_translator.providers import GeminiCLIProvider


class GeminiProviderTests(unittest.TestCase):
    @patch("ebook_gpt_translator.providers.shutil.which", return_value="/usr/bin/gemini")
    @patch("ebook_gpt_translator.providers.subprocess.run")
    def test_translate_uses_gemini_cli(self, mock_run, _mock_which) -> None:
        envelope = {
            "session_id": "test-session",
            "response": json.dumps({"translation": "Hallo Welt"}),
            "stats": {},
        }

        class Result:
            returncode = 0
            stdout = json.dumps(envelope)
            stderr = ""

        mock_run.return_value = Result()

        provider = GeminiCLIProvider(
            ProviderConfig(kind="gemini", model="gemini-2.5-pro"),
            TranslationConfig(),
        )
        result = provider.translate("Hello world", "System prompt")

        self.assertEqual(result.text, "Hallo Welt")
        cmd = mock_run.call_args[0][0]
        self.assertIn("-p", cmd)
        self.assertIn("-o", cmd)
        self.assertIn("json", cmd)
        self.assertIn("-m", cmd)
        self.assertIn("gemini-2.5-pro", cmd)

    @patch("ebook_gpt_translator.providers.shutil.which", return_value="/usr/bin/gemini")
    @patch("ebook_gpt_translator.providers.subprocess.run")
    def test_extract_raw_response_fallback(self, mock_run, _mock_which) -> None:
        """When Gemini returns plain text in response instead of JSON."""
        envelope = {
            "session_id": "test-session",
            "response": "Hallo Welt",
            "stats": {},
        }

        class Result:
            returncode = 0
            stdout = json.dumps(envelope)
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
    def test_strips_markdown_fences_in_response(self, mock_run, _mock_which) -> None:
        envelope = {
            "session_id": "test-session",
            "response": '```json\n{"translation": "Bonjour"}\n```',
            "stats": {},
        }

        class Result:
            returncode = 0
            stdout = json.dumps(envelope)
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

        def fake_run(cmd, **kwargs):
            calls["count"] += 1

            class Result:
                returncode = 0
                stderr = ""

            r = Result()
            if calls["count"] == 1:
                r.stdout = json.dumps({"session_id": "s", "response": "", "stats": {}})
            else:
                r.stdout = json.dumps({
                    "session_id": "s",
                    "response": json.dumps({"translation": "Bonjour"}),
                    "stats": {},
                })
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
