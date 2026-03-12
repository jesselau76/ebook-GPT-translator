from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Asset:
    asset_id: str
    href: str
    media_type: str
    data: bytes


@dataclass(slots=True)
class Block:
    block_id: str
    kind: str
    role: str = "paragraph"
    text: str = ""
    translated_text: str = ""
    asset_id: str | None = None

    @property
    def is_text(self) -> bool:
        return self.kind == "text"


@dataclass(slots=True)
class Chapter:
    chapter_id: str
    title: str
    translated_title: str = ""
    source_href: str | None = None
    blocks: list[Block] = field(default_factory=list)


@dataclass(slots=True)
class Document:
    source_path: Path
    format_name: str
    title: str
    author: str = ""
    language: str = "en"
    chapters: list[Chapter] = field(default_factory=list)
    assets: dict[str, Asset] = field(default_factory=dict)

    def iter_text_blocks(self) -> list[tuple[Chapter, Block]]:
        pairs: list[tuple[Chapter, Block]] = []
        for chapter in self.chapters:
            for block in chapter.blocks:
                if block.is_text and block.text.strip():
                    pairs.append((chapter, block))
        return pairs


@dataclass(slots=True)
class UsageStats:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_hits: int = 0
    api_calls: int = 0
    translated_blocks: int = 0


@dataclass(slots=True)
class OutputArtifacts:
    text_path: Path | None = None
    epub_path: Path | None = None
    manifest_path: Path | None = None
    memory_path: Path | None = None


@dataclass(slots=True)
class TranslationContext:
    document_title: str = ""
    chapter_title: str = ""
    chapter_summary: str = ""
    previous_blocks: list[tuple[str, str]] = field(default_factory=list)
    previous_chunks: list[tuple[str, str]] = field(default_factory=list)
    relevant_terms: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProgressUpdate:
    stage: str
    completed_blocks: int = 0
    total_blocks: int = 0
    current_block_index: int = 0
    current_chunk_index: int = 0
    total_chunks: int = 0
    chapter_title: str = ""
    block_role: str = ""
    message: str = ""
    cache_hits: int = 0
    api_calls: int = 0
