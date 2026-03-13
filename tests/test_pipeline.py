import tempfile
import unittest
import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from ebook_gpt_translator.config import AppConfig
from ebook_gpt_translator.providers import BaseProvider, ProviderResult
from ebook_gpt_translator.pipeline import inspect_resume_state, translate_file


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

            # Heading merged with paragraphs into one block
            merged_text = document.chapters[0].blocks[0].translated_text
            self.assertIn("[German] Chapter 1", merged_text)
            self.assertIn("Hello world.", merged_text)
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
            config.chunking.max_chars = 30
            config.chunking.max_tokens = 30
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

    def test_inspect_resume_state_reports_compatible_and_mismatch_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "sample.txt"
            source.write_text("Chapter 1\n\nAlice met Bob.\n\nBob waved back.", encoding="utf-8")

            config = AppConfig()
            config.provider.kind = "mock"
            config.output.output_dir = str(Path(tmp_dir) / "output")
            config.runtime.cache_path = str(Path(tmp_dir) / ".cache" / "translation.sqlite3")
            config.runtime.job_dir = str(Path(tmp_dir) / ".cache" / "jobs")

            translate_file(source, config)
            compatible = inspect_resume_state(source, config)
            self.assertTrue(compatible.available)
            self.assertTrue(compatible.compatible)
            self.assertGreaterEqual(compatible.completed_blocks, 1)

            changed = AppConfig()
            changed.provider.kind = "mock"
            changed.translation.target_language = "Japanese"
            changed.output.output_dir = config.output.output_dir
            changed.runtime.cache_path = config.runtime.cache_path
            changed.runtime.job_dir = config.runtime.job_dir

            mismatch = inspect_resume_state(source, changed)
            self.assertTrue(mismatch.available)
            self.assertFalse(mismatch.compatible)
            self.assertIn("do not match", mismatch.message)


if __name__ == "__main__":
    unittest.main()
