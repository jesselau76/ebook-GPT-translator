from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


@dataclass(slots=True)
class ProviderConfig:
    kind: str = "codex"
    model: str = "gpt-5.2-codex"
    reasoning_effort: str = "medium"
    api_key: str = ""
    api_base_url: str = ""
    api_version: str = ""
    organization: str = ""
    api_mode: str = "auto"
    timeout_seconds: float = 120.0
    max_retries: int = 5
    proxy: str = ""


@dataclass(slots=True)
class TranslationConfig:
    target_language: str = "Simplified Chinese"
    bilingual_output: bool = False
    custom_prompt: str = ""
    temperature: float = 0.2
    max_output_tokens: int = 0
    preserve_line_breaks: bool = True
    context_window_blocks: int = 6


@dataclass(slots=True)
class ChunkConfig:
    max_chars: int = 5000
    max_tokens: int = 3500
    test_limit: int = 3


@dataclass(slots=True)
class InputConfig:
    start_page: int = 1
    end_page: int = -1


@dataclass(slots=True)
class GlossaryConfig:
    path: str = ""
    case_sensitive: bool = False


@dataclass(slots=True)
class OutputConfig:
    output_dir: str = "output"
    emit_txt: bool = True
    emit_epub: bool = True
    skip_existing: bool = False
    overwrite: bool = False
    write_manifest: bool = True


@dataclass(slots=True)
class RuntimeConfig:
    dry_run: bool = False
    test_mode: bool = False
    cache_path: str = ".cache/translation.sqlite3"
    job_dir: str = ".cache/jobs"


@dataclass(slots=True)
class AppConfig:
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    chunking: ChunkConfig = field(default_factory=ChunkConfig)
    input: InputConfig = field(default_factory=InputConfig)
    glossary: GlossaryConfig = field(default_factory=GlossaryConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _as_int(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    return int(value)


def _as_float(value: Any, default: float) -> float:
    if value in (None, ""):
        return default
    return float(value)


def _merge_section(obj: Any, data: dict[str, Any]) -> None:
    for key, value in data.items():
        if hasattr(obj, key):
            setattr(obj, key, value)


def _legacy_to_dict(parser: configparser.ConfigParser) -> dict[str, dict[str, Any]]:
    settings = parser["option"] if parser.has_section("option") else parser["DEFAULT"]
    return {
        "provider": {
            "kind": settings.get("provider", "codex"),
            "model": settings.get("model", "gpt-5.2-codex"),
            "reasoning_effort": settings.get(
                "reasoning_effort",
                settings.get("reasoning-effort", "medium"),
            ),
            "api_key": settings.get(
                "openai-apikey",
                settings.get("openai_apikey", settings.get("api_key", "")),
            ),
            "api_base_url": settings.get(
                "openai_api_base",
                settings.get(
                    "openai-api-base",
                    settings.get("api_base_url", settings.get("api_base", "")),
                ),
            ),
            "api_version": settings.get("api_version", ""),
            "organization": settings.get("organization", ""),
            "api_mode": settings.get("api_mode", "auto"),
            "proxy": settings.get(
                "openai-proxy",
                settings.get("openai_proxy", settings.get("proxy", "")),
            ),
        },
        "translation": {
            "target_language": settings.get(
                "language",
                settings.get("target-language", settings.get("target_language", "Simplified Chinese")),
            ),
            "bilingual_output": _as_bool(
                settings.get("bilingual-output", settings.get("bilingual_output", False))
            ),
            "custom_prompt": settings.get("prompt", settings.get("custom_prompt", "")),
            "context_window_blocks": _as_int(
                settings.get("context_window_blocks", settings.get("context-window-blocks", "")),
                6,
            ),
        },
        "chunking": {
            "max_chars": _as_int(settings.get("max_len", settings.get("max_chars", "")), 5000),
            "max_tokens": _as_int(settings.get("max_token", settings.get("max_tokens", "")), 3500),
        },
        "input": {
            "start_page": _as_int(settings.get("startpage", settings.get("start_page", "")), 1),
            "end_page": _as_int(settings.get("endpage", settings.get("end_page", "")), -1),
        },
        "glossary": {
            "path": settings.get(
                "transliteration-list",
                settings.get("transliteration_list", settings.get("glossary_path", "")),
            ),
            "case_sensitive": _as_bool(
                settings.get("case-matching", settings.get("case_matching", False))
            ),
        },
        "output": {
            "output_dir": settings.get("output_dir", "output"),
        },
    }


def load_config(config_path: str | None = None, env_file: str | None = None) -> AppConfig:
    if env_file:
        load_dotenv(env_file, override=False)
    else:
        load_dotenv(override=False)

    config = AppConfig()
    path = _detect_config_path(config_path)
    if path:
        if path.suffix.lower() == ".cfg":
            parser = configparser.ConfigParser()
            parser.read(path, encoding="utf-8")
            data = _legacy_to_dict(parser)
        else:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        _merge_config(config, data)

    _apply_env_overrides(config)
    return config


def _detect_config_path(config_path: str | None) -> Path | None:
    if config_path:
        path = Path(config_path)
        return path if path.exists() else None

    for candidate in ("settings.toml", "settings.cfg"):
        path = Path(candidate)
        if path.exists():
            return path
    return None


def _merge_config(config: AppConfig, data: dict[str, Any]) -> None:
    for section_name in ("provider", "translation", "chunking", "input", "glossary", "output", "runtime"):
        section = data.get(section_name, {})
        _merge_section(getattr(config, section_name), section)


def _apply_env_overrides(config: AppConfig) -> None:
    mapping = {
        "EBOOK_TRANSLATOR_PROVIDER": ("provider", "kind"),
        "EBOOK_TRANSLATOR_MODEL": ("provider", "model"),
        "EBOOK_TRANSLATOR_REASONING_EFFORT": ("provider", "reasoning_effort"),
        "EBOOK_TRANSLATOR_API_KEY": ("provider", "api_key"),
        "EBOOK_TRANSLATOR_API_BASE_URL": ("provider", "api_base_url"),
        "EBOOK_TRANSLATOR_API_VERSION": ("provider", "api_version"),
        "EBOOK_TRANSLATOR_API_MODE": ("provider", "api_mode"),
        "EBOOK_TRANSLATOR_PROXY": ("provider", "proxy"),
        "EBOOK_TRANSLATOR_TARGET_LANGUAGE": ("translation", "target_language"),
        "EBOOK_TRANSLATOR_CONTEXT_WINDOW_BLOCKS": ("translation", "context_window_blocks"),
        "EBOOK_TRANSLATOR_GLOSSARY": ("glossary", "path"),
        "EBOOK_TRANSLATOR_OUTPUT_DIR": ("output", "output_dir"),
    }
    for env_name, (section_name, key) in mapping.items():
        value = os.getenv(env_name)
        if value not in (None, ""):
            setattr(getattr(config, section_name), key, value)


def apply_cli_overrides(config: AppConfig, overrides: dict[str, Any]) -> AppConfig:
    for compound_key, value in overrides.items():
        if value is None:
            continue
        section_name, key = compound_key.split(".", 1)
        setattr(getattr(config, section_name), key, value)
    return config


def ensure_runtime_paths(config: AppConfig, base_dir: Path | None = None) -> None:
    root = base_dir or Path.cwd()
    for raw_path in (config.output.output_dir, config.runtime.job_dir):
        (root / raw_path).mkdir(parents=True, exist_ok=True)
    cache_path = root / config.runtime.cache_path
    cache_path.parent.mkdir(parents=True, exist_ok=True)
