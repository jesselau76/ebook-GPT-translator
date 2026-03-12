import tempfile
import unittest
from pathlib import Path

from ebook_gpt_translator.config import load_config


class ConfigTests(unittest.TestCase):
    def test_load_legacy_cfg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "settings.cfg"
            path.write_text(
                "[option]\n"
                "provider = azure\n"
                "model = my-deployment\n"
                "openai-apikey = test-key\n"
                "language = Traditional Chinese\n"
                "bilingual-output = true\n"
                "max_len = 900\n",
                encoding="utf-8",
            )
            config = load_config(str(path))
        self.assertEqual(config.provider.kind, "azure")
        self.assertEqual(config.provider.model, "my-deployment")
        self.assertEqual(config.provider.api_key, "test-key")
        self.assertEqual(config.translation.target_language, "Traditional Chinese")
        self.assertTrue(config.translation.bilingual_output)
        self.assertEqual(config.chunking.max_chars, 900)

    def test_default_provider_is_codex(self) -> None:
        config = load_config(None)
        self.assertEqual(config.provider.kind, "codex")
        self.assertEqual(config.provider.model, "gpt-5.2-codex")
        self.assertEqual(config.provider.reasoning_effort, "medium")
        self.assertEqual(config.translation.context_window_blocks, 6)


if __name__ == "__main__":
    unittest.main()
