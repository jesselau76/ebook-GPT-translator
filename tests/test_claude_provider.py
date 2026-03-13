import unittest
from unittest.mock import patch
import json

from ebook_gpt_translator.config import ProviderConfig, TranslationConfig
from ebook_gpt_translator.providers import ClaudeCodeCLIProvider


class ClaudeProviderTests(unittest.TestCase):
    @patch("ebook_gpt_translator.providers.shutil.which", return_value="/usr/bin/claude")
    @patch("ebook_gpt_translator.providers.subprocess.run")
    def test_translate_uses_claude_cli(self, mock_run, _mock_which) -> None:
        envelope = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": json.dumps({"translation": "Hallo Welt"}),
            "num_turns": 1,
        }

        class Result:
            returncode = 0
            stdout = json.dumps(envelope)
            stderr = ""

        mock_run.return_value = Result()

        provider = ClaudeCodeCLIProvider(
            ProviderConfig(kind="claude", model="claude-sonnet-4-6"),
            TranslationConfig(),
        )
        result = provider.translate("Hello world", "System prompt")

        self.assertEqual(result.text, "Hallo Welt")
        cmd = mock_run.call_args[0][0]
        self.assertIn("-p", cmd)
        self.assertIn("--output-format", cmd)
        self.assertIn("json", cmd)
        self.assertIn("--model", cmd)
        self.assertIn("claude-sonnet-4-6", cmd)
        self.assertIn("--max-turns", cmd)

    @patch("ebook_gpt_translator.providers.shutil.which", return_value="/usr/bin/claude")
    @patch("ebook_gpt_translator.providers.subprocess.run")
    def test_extract_raw_result_fallback(self, mock_run, _mock_which) -> None:
        """When Claude returns plain text in result instead of JSON."""
        envelope = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "Hallo Welt",
            "num_turns": 1,
        }

        class Result:
            returncode = 0
            stdout = json.dumps(envelope)
            stderr = ""

        mock_run.return_value = Result()

        provider = ClaudeCodeCLIProvider(
            ProviderConfig(kind="claude", model="claude-sonnet-4-6"),
            TranslationConfig(),
        )
        result = provider.translate("Hello world", "System prompt")
        self.assertEqual(result.text, "Hallo Welt")

    @patch("ebook_gpt_translator.providers.shutil.which", return_value="/usr/bin/claude")
    @patch("ebook_gpt_translator.providers.subprocess.run")
    def test_handles_error_envelope(self, mock_run, _mock_which) -> None:
        envelope = {
            "type": "result",
            "is_error": True,
            "result": "",
        }

        class Result:
            returncode = 0
            stdout = json.dumps(envelope)
            stderr = ""

        mock_run.return_value = Result()

        provider = ClaudeCodeCLIProvider(
            ProviderConfig(kind="claude", model="claude-sonnet-4-6"),
            TranslationConfig(),
        )
        with self.assertRaises(RuntimeError):
            provider.translate("Hello world", "System prompt")

    @patch("ebook_gpt_translator.providers.shutil.which", return_value=None)
    def test_raises_if_claude_not_found(self, _mock_which) -> None:
        with self.assertRaises(RuntimeError):
            ClaudeCodeCLIProvider(
                ProviderConfig(kind="claude", model="claude-sonnet-4-6"),
                TranslationConfig(),
            )


if __name__ == "__main__":
    unittest.main()
