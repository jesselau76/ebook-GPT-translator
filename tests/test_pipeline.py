import tempfile
import unittest
import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from ebook_gpt_translator.config import AppConfig
from ebook_gpt_translator.providers import BaseProvider, ProviderResult
from ebook_gpt_translator.pipeline import translate_file


class PipelineTests(unittest.TestCase):
    def test_translate_txt_with_mock_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "sample.txt"
            source.write_text("Chapter 1\n\nHello world.\n\nSecond paragraph.", encoding="utf-8")

            config = AppConfig()
            config.provider.kind = "mock"
            config.translation.target_language = "German"
            config.output.output_dir = str(Path(tmp_dir) / "output")
            config.runtime.cache_path = str(Path(tmp_dir) / ".cache" / "translation.sqlite3")
            config.runtime.job_dir = str(Path(tmp_dir) / ".cache" / "jobs")

            document, artifacts, stats = translate_file(source, config)

            self.assertEqual(document.chapters[0].blocks[0].translated_text, "[German] Chapter 1")
            self.assertTrue(artifacts.text_path and artifacts.text_path.exists())
            self.assertTrue(artifacts.epub_path and artifacts.epub_path.exists())
            self.assertTrue(artifacts.memory_path and artifacts.memory_path.exists())
            self.assertEqual(stats.api_calls, 0)

    def test_context_window_is_included_for_consistency(self) -> None:
        class CapturingProvider(BaseProvider):
            is_remote = False

            def __init__(self) -> None:
                self.user_prompts: list[str] = []

            def translate(self, text: str, system_prompt: str, user_prompt: str | None = None) -> ProviderResult:
                _ = system_prompt
                self.user_prompts.append(user_prompt or "")
                return ProviderResult(text=f"T::{text}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "sample.txt"
            source.write_text(
                "Chapter 1\n\nAlice looked at Bob.\n\nBob answered Alice quietly.",
                encoding="utf-8",
            )

            config = AppConfig()
            config.provider.kind = "mock"
            config.translation.context_window_blocks = 2
            config.output.output_dir = str(Path(tmp_dir) / "output")
            config.runtime.cache_path = str(Path(tmp_dir) / ".cache" / "translation.sqlite3")
            config.runtime.job_dir = str(Path(tmp_dir) / ".cache" / "jobs")

            provider = CapturingProvider()
            with patch("ebook_gpt_translator.pipeline.build_provider", return_value=provider):
                _, artifacts, _ = translate_file(source, config)

            self.assertIn("CURRENT_TEXT:\nAlice looked at Bob.", provider.user_prompts[1])
            self.assertIn("PREVIOUS_TRANSLATED_CONTEXT:", provider.user_prompts[2])
            self.assertIn("T::Alice looked at Bob.", provider.user_prompts[2])
            self.assertTrue(artifacts.memory_path and artifacts.memory_path.exists())
            memory_payload = json.loads(artifacts.memory_path.read_text(encoding="utf-8"))
            self.assertIn("term_memory", memory_payload)
            self.assertIn("Alice", memory_payload["term_memory"])

    def test_progress_callback_reports_block_and_chunk_updates(self) -> None:
        events: list[dict[str, object]] = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "sample.txt"
            source.write_text(
                "Chapter 1\n\n"
                + ("This is a deliberately long paragraph. " * 80)
                + "\n\nSecond paragraph.",
                encoding="utf-8",
            )

            config = AppConfig()
            config.provider.kind = "mock"
            config.chunking.max_chars = 200
            config.chunking.max_tokens = 120
            config.output.output_dir = str(Path(tmp_dir) / "output")
            config.runtime.cache_path = str(Path(tmp_dir) / ".cache" / "translation.sqlite3")
            config.runtime.job_dir = str(Path(tmp_dir) / ".cache" / "jobs")

            translate_file(source, config, progress_callback=lambda event: events.append(asdict(event)))

        stages = [str(event["stage"]) for event in events]
        self.assertIn("start", stages)
        self.assertIn("block_started", stages)
        self.assertIn("chunk_started", stages)
        self.assertIn("chunk_finished", stages)
        self.assertIn("block_finished", stages)
        self.assertEqual(stages[-1], "done")
        chunk_events = [event for event in events if event["stage"] == "chunk_started"]
        self.assertTrue(any(int(event["total_chunks"]) > 1 for event in chunk_events))


if __name__ == "__main__":
    unittest.main()
