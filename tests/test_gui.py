import unittest
from unittest.mock import patch

from ebook_gpt_translator.gui import build_config_from_form, load_codex_model_choices


class GuiTests(unittest.TestCase):
    def test_build_config_from_form_applies_defaults(self) -> None:
        config = build_config_from_form(
            {
                "config_path": "",
                "env_file": "",
                "provider": "codex",
                "model": "gpt-5.2-codex",
                "reasoning_effort": "low",
                "api_key": "",
                "api_base_url": "",
                "api_version": "",
                "api_mode": "auto",
                "target_language": "Japanese",
                "custom_prompt": "Use a literary style.",
                "context_window": 8,
                "glossary_path": "",
                "bilingual": True,
                "dry_run": False,
                "test_mode": False,
                "test_limit": 3,
                "max_chars": 2000,
                "max_tokens": 1400,
                "start_page": 1,
                "end_page": -1,
                "output_dir": "output",
                "txt_only": False,
                "epub_only": False,
                "skip_existing": False,
                "overwrite": False,
            }
        )
        self.assertEqual(config.provider.kind, "codex")
        self.assertEqual(config.provider.model, "gpt-5.2-codex")
        self.assertEqual(config.provider.reasoning_effort, "low")
        self.assertEqual(config.translation.target_language, "Japanese")
        self.assertEqual(config.translation.custom_prompt, "Use a literary style.")
        self.assertEqual(config.translation.context_window_blocks, 8)
        self.assertTrue(config.translation.bilingual_output)

    def test_load_codex_model_choices_returns_defaults_when_empty(self) -> None:
        with patch("ebook_gpt_translator.cli._load_codex_models", return_value=[]):
            choices = load_codex_model_choices()
        self.assertIn("gpt-5.2-codex", choices)


if __name__ == "__main__":
    unittest.main()
