from __future__ import annotations

import re

try:
    import tiktoken
except ModuleNotFoundError:  # pragma: no cover
    tiktoken = None


_SENTENCE_BREAK_RE = re.compile(r"(?<=[.!?。！？])\s+")


def estimate_tokens(text: str, model: str = "") -> int:
    if not text:
        return 0
    if tiktoken is None:
        return max(1, len(text) // 4)
    try:
        encoding = tiktoken.encoding_for_model(model or "gpt-4o-mini")
        return len(encoding.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def split_text(text: str, max_chars: int, max_tokens: int, model: str = "") -> list[str]:
    if len(text) <= max_chars and estimate_tokens(text, model) <= max_tokens:
        return [text]

    chunks: list[str] = []
    for paragraph in _split_paragraphs(text):
        if len(paragraph) <= max_chars and estimate_tokens(paragraph, model) <= max_tokens:
            chunks.append(paragraph)
            continue
        chunks.extend(_split_sentences(paragraph, max_chars, max_tokens, model))
    return [chunk for chunk in chunks if chunk.strip()]


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    return paragraphs or [text]


def _split_sentences(text: str, max_chars: int, max_tokens: int, model: str) -> list[str]:
    sentences = [part.strip() for part in _SENTENCE_BREAK_RE.split(text) if part.strip()]
    if not sentences:
        return _hard_split(text, max_chars)

    results: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        candidate = " ".join(current + [sentence]).strip()
        if current and (len(candidate) > max_chars or estimate_tokens(candidate, model) > max_tokens):
            results.append(" ".join(current).strip())
            current = [sentence]
            continue
        if not current and (len(sentence) > max_chars or estimate_tokens(sentence, model) > max_tokens):
            results.extend(_hard_split(sentence, max_chars))
            continue
        current.append(sentence)
    if current:
        results.append(" ".join(current).strip())
    return results


def _hard_split(text: str, max_chars: int) -> list[str]:
    return [text[index : index + max_chars].strip() for index in range(0, len(text), max_chars)]
