from __future__ import annotations

from pathlib import Path

from ebook_gpt_translator.cli import app


def main() -> None:
    app(prog_name="text_translation.py")


def translate_legacy(input_path: str) -> None:
    app(["translate", str(Path(input_path))], prog_name="text_translation.py")

