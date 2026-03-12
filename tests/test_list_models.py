import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ebook_gpt_translator.cli import _load_codex_models


class ListModelsTests(unittest.TestCase):
    def test_load_codex_models_from_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            home = Path(tmp_dir)
            cache_dir = home / ".codex"
            cache_dir.mkdir(parents=True)
            (cache_dir / "models_cache.json").write_text(
                '{"models":[{"slug":"gpt-5.2-codex","default_reasoning_level":"medium","supported_reasoning_levels":[{"effort":"low"},{"effort":"medium"}]}]}',
                encoding="utf-8",
            )
            with patch("ebook_gpt_translator.cli.Path.home", return_value=home):
                models = _load_codex_models()
        self.assertEqual(models[0]["slug"], "gpt-5.2-codex")


if __name__ == "__main__":
    unittest.main()
