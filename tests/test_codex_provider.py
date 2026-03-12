import unittest
from unittest.mock import patch

from ebook_gpt_translator.config import ProviderConfig, TranslationConfig
from ebook_gpt_translator.providers import CodexCLIProvider


class CodexProviderTests(unittest.TestCase):
    @patch("ebook_gpt_translator.providers.shutil.which", return_value="/usr/bin/codex")
    @patch("ebook_gpt_translator.providers.subprocess.run")
    def test_translate_uses_codex_cli(self, mock_run, _mock_which) -> None:
        def fake_run(cmd, input, text, capture_output, check, timeout):
            output_path = cmd[cmd.index("-o") + 1]
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write("Hallo Welt")

            class Result:
                returncode = 0
                stderr = ""

            self.assertIn("System prompt", input)
            self.assertIn("Hello world", input)
            self.assertIn("-s", cmd)
            self.assertIn("read-only", cmd)
            self.assertIn("-m", cmd)
            self.assertIn("gpt-5.2-codex", cmd)
            self.assertIn('-c', cmd)
            self.assertIn('model_reasoning_effort="medium"', cmd)
            return Result()

        mock_run.side_effect = fake_run

        provider = CodexCLIProvider(
            ProviderConfig(kind="codex", model="gpt-5.2-codex", reasoning_effort="medium"),
            TranslationConfig(),
        )
        result = provider.translate("Hello world", "System prompt")

        self.assertEqual(result.text, "Hallo Welt")


if __name__ == "__main__":
    unittest.main()
