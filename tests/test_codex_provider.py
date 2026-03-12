import unittest
from unittest.mock import patch
import json

from ebook_gpt_translator.config import ProviderConfig, TranslationConfig
from ebook_gpt_translator.providers import CodexCLIProvider


class CodexProviderTests(unittest.TestCase):
    @patch("ebook_gpt_translator.providers.shutil.which", return_value="/usr/bin/codex")
    @patch("ebook_gpt_translator.providers.subprocess.run")
    def test_translate_uses_codex_cli(self, mock_run, _mock_which) -> None:
        def fake_run(cmd, input, text, capture_output, check, timeout):
            output_path = cmd[cmd.index("-o") + 1]
            schema_path = cmd[cmd.index("--output-schema") + 1]
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump({"translation": "Hallo Welt"}, handle)

            with open(schema_path, "r", encoding="utf-8") as handle:
                schema = json.load(handle)

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            self.assertIn("System prompt", input)
            self.assertIn("Hello world", input)
            self.assertIn("Return a JSON object", input)
            self.assertIn("-s", cmd)
            self.assertIn("read-only", cmd)
            self.assertIn("-m", cmd)
            self.assertIn("gpt-5.2-codex", cmd)
            self.assertIn("-c", cmd)
            self.assertIn('model_reasoning_effort="medium"', cmd)
            self.assertEqual(schema["required"], ["translation"])
            return Result()

        mock_run.side_effect = fake_run

        provider = CodexCLIProvider(
            ProviderConfig(kind="codex", model="gpt-5.2-codex", reasoning_effort="medium"),
            TranslationConfig(),
        )
        result = provider.translate("Hello world", "System prompt")

        self.assertEqual(result.text, "Hallo Welt")

    @patch("ebook_gpt_translator.providers.shutil.which", return_value="/usr/bin/codex")
    @patch("ebook_gpt_translator.providers.subprocess.run")
    def test_translate_retries_after_empty_structured_output(self, mock_run, _mock_which) -> None:
        calls = {"count": 0}

        def fake_run(cmd, input, text, capture_output, check, timeout):
            output_path = cmd[cmd.index("-o") + 1]
            calls["count"] += 1
            with open(output_path, "w", encoding="utf-8") as handle:
                if calls["count"] == 1:
                    handle.write("")
                else:
                    json.dump({"translation": "Bonjour"}, handle)

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        mock_run.side_effect = fake_run

        provider = CodexCLIProvider(
            ProviderConfig(kind="codex", model="gpt-5.2-codex", reasoning_effort="medium"),
            TranslationConfig(),
        )
        result = provider.translate("Hello world", "System prompt")

        self.assertEqual(result.text, "Bonjour")
        self.assertEqual(calls["count"], 2)


if __name__ == "__main__":
    unittest.main()
