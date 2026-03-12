import tempfile
import unittest
from pathlib import Path

from ebook_gpt_translator.cli import _mask_secret, _read_env_file, _write_env_updates


class AuthCliTests(unittest.TestCase):
    def test_write_env_updates_merges_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text("EXISTING=value\n", encoding="utf-8")
            _write_env_updates(
                env_file,
                {
                    "EBOOK_TRANSLATOR_PROVIDER": "openai",
                    "EBOOK_TRANSLATOR_API_KEY": "sk-test-12345678",
                },
            )
            values = _read_env_file(env_file)
        self.assertEqual(values["EXISTING"], "value")
        self.assertEqual(values["EBOOK_TRANSLATOR_PROVIDER"], "openai")
        self.assertEqual(values["EBOOK_TRANSLATOR_API_KEY"], "sk-test-12345678")

    def test_mask_secret(self) -> None:
        self.assertEqual(_mask_secret("abcdefgh12345678"), "abcd...5678")


if __name__ == "__main__":
    unittest.main()
