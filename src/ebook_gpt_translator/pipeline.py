from __future__ import annotations

import json
import re
import hashlib
from collections import deque
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ebook_gpt_translator.cache import TranslationCache, write_manifest
from ebook_gpt_translator.chunking import split_text
from ebook_gpt_translator.config import AppConfig, ensure_runtime_paths
from ebook_gpt_translator.documents import load_document, write_outputs
from ebook_gpt_translator.glossary import Glossary
from ebook_gpt_translator.models import (
    Document,
    OutputArtifacts,
    ProgressUpdate,
    ResumeStatus,
    TranslationContext,
    UsageStats,
)
from ebook_gpt_translator.providers import BaseProvider, build_provider


console = Console()
ProgressCallback = Callable[[ProgressUpdate], None]
_TERM_STOPWORDS = {
    "The",
    "A",
    "An",
    "And",
    "But",
    "Or",
    "If",
    "Then",
    "When",
    "After",
    "Before",
    "He",
    "She",
    "They",
    "We",
    "I",
    "You",
    "It",
    "His",
    "Her",
    "Their",
    "This",
    "That",
    "These",
    "Those",
}
_HONORIFIC_RE = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Professor|Captain|Capt|Sir|Lady|Lord|Saint|St|King|Queen|Prince|Princess)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b"
)
_MULTI_WORD_TERM_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b")
_ALL_CAPS_TERM_RE = re.compile(r"\b[A-Z]{2,}(?:-[A-Z]{2,})*\b")
_SINGLE_CAP_TERM_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")


def translate_file(
    input_path: Path,
    config: AppConfig,
    progress_callback: ProgressCallback | None = None,
) -> tuple[Document, OutputArtifacts, UsageStats]:
    ensure_runtime_paths(config)

    document = load_document(input_path, config)
    provider = build_provider(config.provider, config.translation)
    glossary = Glossary.from_path(config.glossary.path, config.glossary.case_sensitive)
    cache = TranslationCache(Path(config.runtime.cache_path))
    stats = UsageStats()
    memory_path = _memory_path(config, input_path)
    resume_fingerprint = _build_resume_fingerprint(input_path, config)
    try:
        memory_state = _load_memory_state(memory_path, resume_fingerprint)
        _translate_document(
            document,
            config,
            provider,
            glossary,
            cache,
            stats,
            memory_state,
            memory_path,
            resume_fingerprint,
            progress_callback,
        )
        text_path, epub_path = write_outputs(document, config)
        manifest_path = None
        if config.output.write_manifest:
            manifest_path = _manifest_path(config, input_path)
            write_manifest(
                manifest_path,
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "input_file": str(input_path),
                    "output": {
                        "text_path": str(text_path) if text_path else "",
                        "epub_path": str(epub_path) if epub_path else "",
                        "memory_path": str(memory_path),
                    },
                    "config": {
                        "provider": asdict(config.provider),
                        "translation": asdict(config.translation),
                        "chunking": asdict(config.chunking),
                        "input": asdict(config.input),
                        "glossary": asdict(config.glossary),
                        "output": asdict(config.output),
                        "runtime": asdict(config.runtime),
                    },
                    "memory": {
                        "chapter_count": len(memory_state["chapter_memories"]),
                        "term_count": len(memory_state["term_memory"]),
                    },
                },
                stats,
            )
        return (
            document,
            OutputArtifacts(
                text_path=text_path,
                epub_path=epub_path,
                manifest_path=manifest_path,
                memory_path=memory_path,
            ),
            stats,
        )
    finally:
        cache.close()


def _translate_document(
    document: Document,
    config: AppConfig,
    provider: BaseProvider,
    glossary: Glossary,
    cache: TranslationCache,
    stats: UsageStats,
    memory_state: dict,
    memory_path: Path,
    resume_fingerprint: str,
    progress_callback: ProgressCallback | None = None,
) -> None:
    system_prompt = _build_system_prompt(config, glossary)
    text_blocks = document.iter_text_blocks()
    if config.runtime.test_mode:
        text_blocks = text_blocks[: config.chunking.test_limit]
    recent_blocks: deque[tuple[str, str]] = deque(
        memory_state["recent_blocks"],
        maxlen=max(0, config.translation.context_window_blocks),
    )
    chapter_memories: dict[str, deque[str]] = {
        chapter_id: deque(items, maxlen=8)
        for chapter_id, items in memory_state["chapter_memories"].items()
    }
    term_memory: dict[str, dict[str, str | int]] = memory_state["term_memory"]
    document_term_counts = _scan_document_term_counts(document)
    total_blocks = len(text_blocks)

    _emit_progress(
        progress_callback,
        ProgressUpdate(
            stage="start",
            total_blocks=total_blocks,
            message=f"Loaded {total_blocks} text blocks from {document.title or document.source_path.name}.",
        ),
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Translating", total=total_blocks or 1)
        for block_index, (chapter, block) in enumerate(text_blocks, start=1):
            source_text = glossary.apply(block.text)
            block_terms = _extract_candidate_terms(source_text, document_term_counts)
            chapter_memory = chapter_memories.setdefault(chapter.chapter_id, deque(maxlen=8))
            _emit_progress(
                progress_callback,
                ProgressUpdate(
                    stage="block_started",
                    completed_blocks=stats.translated_blocks,
                    total_blocks=total_blocks,
                    current_block_index=block_index,
                    chapter_title=chapter.translated_title or chapter.title,
                    block_role=block.role,
                    message=_describe_block(block_index, total_blocks, chapter, block),
                    cache_hits=stats.cache_hits,
                    api_calls=stats.api_calls,
                ),
            )
            context = TranslationContext(
                document_title=document.title,
                chapter_title=chapter.translated_title or chapter.title,
                chapter_summary=_build_chapter_summary(chapter_memory),
                previous_blocks=list(recent_blocks),
                relevant_terms=_build_relevant_term_memory(block_terms, term_memory),
            )
            translated = _translate_text(
                source_text,
                config,
                provider,
                system_prompt,
                cache,
                stats,
                context,
                block_index,
                total_blocks,
                chapter.translated_title or chapter.title,
                block.role,
                progress_callback,
            )
            block.translated_text = translated
            if block.role == "heading" and chapter.title == block.text:
                chapter.translated_title = translated
            chapter_memory.append(translated)
            recent_blocks.append((source_text, translated))
            _update_term_memory(term_memory, block_terms, source_text, translated)
            _save_memory_state(
                memory_path,
                recent_blocks,
                chapter_memories,
                term_memory,
                stats.translated_blocks + 1,
                total_blocks,
                resume_fingerprint,
            )
            stats.translated_blocks += 1
            progress.advance(task)
            _emit_progress(
                progress_callback,
                ProgressUpdate(
                    stage="block_finished",
                    completed_blocks=stats.translated_blocks,
                    total_blocks=total_blocks,
                    current_block_index=block_index,
                    chapter_title=chapter.translated_title or chapter.title,
                    block_role=block.role,
                    message=_describe_block(block_index, total_blocks, chapter, block, finished=True),
                    cache_hits=stats.cache_hits,
                    api_calls=stats.api_calls,
                ),
            )

    _emit_progress(
        progress_callback,
        ProgressUpdate(
            stage="done",
            completed_blocks=stats.translated_blocks,
            total_blocks=total_blocks,
            message=f"Translated {stats.translated_blocks}/{total_blocks} blocks.",
            cache_hits=stats.cache_hits,
            api_calls=stats.api_calls,
        ),
    )


def _translate_text(
    text: str,
    config: AppConfig,
    provider: BaseProvider,
    system_prompt: str,
    cache: TranslationCache,
    stats: UsageStats,
    context: TranslationContext,
    block_index: int,
    total_blocks: int,
    chapter_title: str,
    block_role: str,
    progress_callback: ProgressCallback | None = None,
) -> str:
    chunks = split_text(
        text=text,
        max_chars=config.chunking.max_chars,
        max_tokens=config.chunking.max_tokens,
        model=config.provider.model,
    )
    translated_parts: list[str] = []
    local_context = TranslationContext(
        document_title=context.document_title,
        chapter_title=context.chapter_title,
        previous_blocks=context.previous_blocks,
    )
    total_chunks = len(chunks)
    for chunk_index, chunk in enumerate(chunks, start=1):
        local_context.previous_chunks = list(zip(chunks[: len(translated_parts)], translated_parts))
        _emit_progress(
            progress_callback,
            ProgressUpdate(
                stage="chunk_started",
                completed_blocks=stats.translated_blocks,
                total_blocks=total_blocks,
                current_block_index=block_index,
                current_chunk_index=chunk_index,
                total_chunks=total_chunks,
                chapter_title=chapter_title,
                block_role=block_role,
                message=(
                    f"Translating block {block_index}/{total_blocks}, "
                    f"chunk {chunk_index}/{total_chunks}."
                ),
                cache_hits=stats.cache_hits,
                api_calls=stats.api_calls,
            ),
        )
        user_prompt = _build_user_prompt(chunk, local_context)
        payload = {
            "provider": config.provider.kind,
            "model": config.provider.model,
            "reasoning_effort": config.provider.reasoning_effort,
            "api_mode": config.provider.api_mode,
            "target_language": config.translation.target_language,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "temperature": str(config.translation.temperature),
            "chunk": chunk,
        }
        cached = cache.get(payload)
        if cached is not None:
            translated_text, usage = cached
            stats.cache_hits += 1
            stats.prompt_tokens += usage.get("prompt_tokens", 0)
            stats.completion_tokens += usage.get("completion_tokens", 0)
            translated_parts.append(translated_text)
            _emit_progress(
                progress_callback,
                ProgressUpdate(
                    stage="chunk_finished",
                    completed_blocks=stats.translated_blocks,
                    total_blocks=total_blocks,
                    current_block_index=block_index,
                    current_chunk_index=chunk_index,
                    total_chunks=total_chunks,
                    chapter_title=chapter_title,
                    block_role=block_role,
                    message=(
                        f"Used cache for block {block_index}/{total_blocks}, "
                        f"chunk {chunk_index}/{total_chunks}."
                    ),
                    cache_hits=stats.cache_hits,
                    api_calls=stats.api_calls,
                ),
            )
            continue

        if config.runtime.dry_run:
            translated_text = _dry_run_text(chunk, config.translation.target_language)
            usage = {"prompt_tokens": 0, "completion_tokens": 0}
        else:
            result = provider.translate(chunk, system_prompt, user_prompt)
            translated_text = result.text
            usage = {
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
            }
            if provider.is_remote:
                stats.api_calls += 1
            stats.prompt_tokens += result.prompt_tokens
            stats.completion_tokens += result.completion_tokens
        cache.put(payload, translated_text, usage)
        translated_parts.append(translated_text)
        _emit_progress(
            progress_callback,
            ProgressUpdate(
                stage="chunk_finished",
                completed_blocks=stats.translated_blocks,
                total_blocks=total_blocks,
                current_block_index=block_index,
                current_chunk_index=chunk_index,
                total_chunks=total_chunks,
                chapter_title=chapter_title,
                block_role=block_role,
                message=(
                    f"Finished block {block_index}/{total_blocks}, "
                    f"chunk {chunk_index}/{total_chunks}."
                ),
                cache_hits=stats.cache_hits,
                api_calls=stats.api_calls,
            ),
        )
    return _join_chunks(translated_parts)


def _emit_progress(progress_callback: ProgressCallback | None, event: ProgressUpdate) -> None:
    if progress_callback is not None:
        progress_callback(event)


def _describe_block(
    block_index: int,
    total_blocks: int,
    chapter,
    block,
    finished: bool = False,
) -> str:
    action = "Finished" if finished else "Starting"
    chapter_title = chapter.translated_title or chapter.title or "Untitled chapter"
    return f"{action} block {block_index}/{total_blocks} in {chapter_title} [{block.role}]"


def _join_chunks(parts: list[str]) -> str:
    joined = "\n\n".join(part.strip() for part in parts if part.strip()).strip()
    return re.sub(r"\n{3,}", "\n\n", joined)


def _build_system_prompt(config: AppConfig, glossary: Glossary) -> str:
    lines = [
        "You are a professional literary translator.",
        f"Translate the user's content into {config.translation.target_language}.",
        "Preserve meaning, tone, proper nouns, and paragraph boundaries.",
        "Use any supplied prior context only to maintain consistency of names, terminology, tense, and voice.",
        "Keep person names, place names, titles, and domain terms fully consistent across the whole book.",
        "Translate only the CURRENT_TEXT section.",
        "Return only the translated text without commentary.",
    ]
    if config.translation.preserve_line_breaks:
        lines.append("Preserve line breaks whenever practical.")
    if config.translation.custom_prompt.strip():
        lines.append(config.translation.custom_prompt.strip())
    glossary_suffix = glossary.as_prompt_suffix()
    if glossary_suffix:
        lines.append(glossary_suffix)
    return "\n".join(lines)


def _dry_run_text(text: str, target_language: str) -> str:
    return f"[DRY RUN -> {target_language}] {text}"


def _manifest_path(config: AppConfig, input_path: Path) -> Path:
    safe_name = input_path.stem.replace(" ", "_")
    return Path(config.runtime.job_dir) / f"{safe_name}.manifest.json"


def _memory_path(config: AppConfig, input_path: Path) -> Path:
    safe_name = input_path.stem.replace(" ", "_")
    return Path(config.runtime.job_dir) / f"{safe_name}.memory.json"


def inspect_resume_state(input_path: Path, config: AppConfig) -> ResumeStatus:
    ensure_runtime_paths(config)
    memory_path = _memory_path(config, input_path)
    if not memory_path.exists():
        return ResumeStatus(message="No saved resume state was found for this file.")

    try:
        payload = json.loads(memory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ResumeStatus(
            available=True,
            compatible=False,
            memory_path=memory_path,
            message="A resume file exists but could not be read.",
        )

    expected_fingerprint = _build_resume_fingerprint(input_path, config)
    stored_fingerprint = str(payload.get("resume_fingerprint", ""))
    completed_blocks = int(payload.get("completed_blocks", 0) or 0)
    total_blocks = int(payload.get("total_blocks", 0) or 0)
    compatible = stored_fingerprint == expected_fingerprint and completed_blocks > 0

    if compatible:
        message = f"Resume available: {completed_blocks}/{total_blocks or '?'} blocks already completed."
    elif completed_blocks > 0:
        message = "Saved progress exists, but the current settings do not match the previous run."
    else:
        message = "A resume file exists, but no completed blocks were recorded yet."

    return ResumeStatus(
        available=True,
        compatible=compatible,
        completed_blocks=completed_blocks,
        total_blocks=total_blocks,
        message=message,
        memory_path=memory_path,
    )


def _build_user_prompt(text: str, context: TranslationContext) -> str:
    sections = [
        "Translate the CURRENT_TEXT section into the requested target language.",
        "Keep terminology, naming, and narrative voice consistent with the reference context.",
    ]
    if context.document_title:
        sections.append(f"BOOK_TITLE:\n{context.document_title}")
    if context.chapter_title:
        sections.append(f"CHAPTER_TITLE:\n{context.chapter_title}")
    if context.chapter_summary:
        sections.append(f"CHAPTER_MEMORY_SUMMARY:\n{context.chapter_summary}")
    if context.relevant_terms:
        sections.append("CONSISTENCY_TERM_MEMORY:\n" + "\n".join(f"- {line}" for line in context.relevant_terms))
    if context.previous_blocks:
        previous_blocks = []
        for index, (source, translated) in enumerate(context.previous_blocks, start=1):
            previous_blocks.append(
                f"[Context {index} Source]\n{source}\n[Context {index} Translation]\n{translated}"
            )
        sections.append("PREVIOUS_TRANSLATED_CONTEXT:\n" + "\n\n".join(previous_blocks))
    if context.previous_chunks:
        previous_chunks = []
        for index, (source, translated) in enumerate(context.previous_chunks, start=1):
            previous_chunks.append(
                f"[Same Block Part {index} Source]\n{source}\n[Same Block Part {index} Translation]\n{translated}"
            )
        sections.append("PREVIOUS_SEGMENTS_IN_SAME_BLOCK:\n" + "\n\n".join(previous_chunks))
    sections.append(f"CURRENT_TEXT:\n{text}")
    return "\n\n".join(sections)


def _scan_document_term_counts(document: Document) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, block in document.iter_text_blocks():
        for term in _extract_raw_terms(block.text):
            counts[term] = counts.get(term, 0) + 1
    return counts


def _extract_raw_terms(text: str) -> list[str]:
    terms: list[str] = []
    for pattern in (_HONORIFIC_RE, _MULTI_WORD_TERM_RE, _ALL_CAPS_TERM_RE):
        terms.extend(match.group(0).strip() for match in pattern.finditer(text))

    for match in _SINGLE_CAP_TERM_RE.finditer(text):
        word = match.group(0).strip()
        if word not in _TERM_STOPWORDS:
            terms.append(word)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in sorted(terms, key=len, reverse=True):
        if term not in seen:
            seen.add(term)
            deduped.append(term)
    return deduped


def _extract_candidate_terms(text: str, term_counts: dict[str, int]) -> list[str]:
    candidates: list[str] = []
    for term in _extract_raw_terms(text):
        if " " in term or term.isupper() or term_counts.get(term, 0) >= 2 or _HONORIFIC_RE.fullmatch(term):
            candidates.append(term)
    return candidates[:12]


def _update_term_memory(
    term_memory: dict[str, dict[str, str | int]],
    block_terms: list[str],
    source_text: str,
    translated_text: str,
) -> None:
    for term in block_terms:
        entry = term_memory.get(term, {"count": 0})
        entry["count"] = int(entry["count"]) + 1
        entry["source_excerpt"] = _clip_text(source_text, 160)
        entry["translated_excerpt"] = _clip_text(translated_text, 160)
        term_memory[term] = entry


def _build_relevant_term_memory(
    block_terms: list[str],
    term_memory: dict[str, dict[str, str | int]],
) -> list[str]:
    lines: list[str] = []
    for term in block_terms:
        entry = term_memory.get(term)
        if not entry:
            continue
        source_excerpt = str(entry.get("source_excerpt", ""))
        translated_excerpt = str(entry.get("translated_excerpt", ""))
        lines.append(
            f"{term} | prior source: {source_excerpt} | prior translation: {translated_excerpt}"
        )
    return lines[:10]


def _build_chapter_summary(chapter_memory: deque[str]) -> str:
    if not chapter_memory:
        return ""
    summary_bits: list[str] = []
    for translated in list(chapter_memory)[-4:]:
        first_sentence = re.split(r"(?<=[.!?。！？])\s+", translated.strip(), maxsplit=1)[0]
        if first_sentence:
            summary_bits.append(_clip_text(first_sentence, 180))
    return " ".join(summary_bits)[:800]


def _clip_text(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _load_memory_state(memory_path: Path, resume_fingerprint: str) -> dict:
    if not memory_path.exists():
        return {
            "recent_blocks": [],
            "chapter_memories": {},
            "term_memory": {},
            "completed_blocks": 0,
            "total_blocks": 0,
        }
    data = json.loads(memory_path.read_text(encoding="utf-8"))
    if str(data.get("resume_fingerprint", "")) != resume_fingerprint:
        return {
            "recent_blocks": [],
            "chapter_memories": {},
            "term_memory": {},
            "completed_blocks": 0,
            "total_blocks": 0,
        }
    return {
        "recent_blocks": [],
        "chapter_memories": {},
        "term_memory": {},
        "completed_blocks": int(data.get("completed_blocks", 0) or 0),
        "total_blocks": int(data.get("total_blocks", 0) or 0),
    }


def _save_memory_state(
    memory_path: Path,
    recent_blocks: deque[tuple[str, str]],
    chapter_memories: dict[str, deque[str]],
    term_memory: dict[str, dict[str, str | int]],
    completed_blocks: int,
    total_blocks: int,
    resume_fingerprint: str,
) -> None:
    payload = {
        "recent_blocks": list(recent_blocks),
        "chapter_memories": {
            chapter_id: list(memory)
            for chapter_id, memory in chapter_memories.items()
        },
        "term_memory": term_memory,
        "completed_blocks": completed_blocks,
        "total_blocks": total_blocks,
        "resume_fingerprint": resume_fingerprint,
    }
    memory_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_resume_fingerprint(input_path: Path, config: AppConfig) -> str:
    glossary_path = Path(config.glossary.path) if config.glossary.path else None
    payload = {
        "input": _path_signature(input_path),
        "glossary": _path_signature(glossary_path) if glossary_path else None,
        "provider": {
            "kind": config.provider.kind,
            "model": config.provider.model,
            "reasoning_effort": config.provider.reasoning_effort,
            "api_mode": config.provider.api_mode,
            "api_base_url": config.provider.api_base_url,
        },
        "translation": {
            "target_language": config.translation.target_language,
            "custom_prompt": config.translation.custom_prompt,
            "preserve_line_breaks": config.translation.preserve_line_breaks,
            "context_window_blocks": config.translation.context_window_blocks,
        },
        "chunking": {
            "max_chars": config.chunking.max_chars,
            "max_tokens": config.chunking.max_tokens,
        },
        "input_options": {
            "start_page": config.input.start_page,
            "end_page": config.input.end_page,
        },
        "runtime": {
            "dry_run": config.runtime.dry_run,
            "test_mode": config.runtime.test_mode,
        },
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _path_signature(path: Path | None) -> dict[str, str | int] | None:
    if path is None:
        return None
    try:
        stat = path.stat()
    except OSError:
        return {"path": str(path), "exists": 0}
    return {
        "path": str(path.resolve()),
        "exists": 1,
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }
