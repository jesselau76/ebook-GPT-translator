from __future__ import annotations

import itertools
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from openai import AzureOpenAI, OpenAI

from ebook_gpt_translator.config import ProviderConfig, TranslationConfig


@dataclass(slots=True)
class ProviderResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class BaseProvider:
    is_remote = True

    def translate(self, text: str, system_prompt: str, user_prompt: str | None = None) -> ProviderResult:
        raise NotImplementedError


class MockProvider(BaseProvider):
    is_remote = False

    def __init__(self, translation: TranslationConfig) -> None:
        self.target_language = translation.target_language

    def translate(self, text: str, system_prompt: str, user_prompt: str | None = None) -> ProviderResult:
        _ = system_prompt, user_prompt
        return ProviderResult(text=f"[{self.target_language}] {text}")


class OpenAICompatibleProvider(BaseProvider):
    def __init__(self, provider: ProviderConfig, translation: TranslationConfig) -> None:
        self.provider_config = provider
        self.translation_config = translation
        self.api_keys = [part.strip() for part in provider.api_key.split(",") if part.strip()]
        self._key_cycle = itertools.cycle(self.api_keys or [""])

    def _client_kwargs(self, api_key: str) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": self.provider_config.timeout_seconds,
            "max_retries": self.provider_config.max_retries,
        }
        if self.provider_config.organization:
            kwargs["organization"] = self.provider_config.organization
        if self.provider_config.proxy:
            kwargs["http_client"] = httpx.Client(proxy=self.provider_config.proxy)
        if self.provider_config.api_base_url:
            kwargs["base_url"] = self.provider_config.api_base_url
        return kwargs

    def _build_client(self, api_key: str) -> Any:
        if self.provider_config.kind == "azure":
            kwargs = self._client_kwargs(api_key)
            kwargs["azure_endpoint"] = self.provider_config.api_base_url
            kwargs["api_version"] = self.provider_config.api_version or "2024-02-01"
            kwargs.pop("base_url", None)
            return AzureOpenAI(**kwargs)
        return OpenAI(**self._client_kwargs(api_key))

    def translate(self, text: str, system_prompt: str, user_prompt: str | None = None) -> ProviderResult:
        api_key = next(self._key_cycle)
        client = self._build_client(api_key)
        api_mode = (self.provider_config.api_mode or "auto").lower()
        prompt_text = user_prompt or text
        if api_mode in {"auto", "responses"} and hasattr(client, "responses") and self.provider_config.kind != "azure":
            response = client.responses.create(
                model=self.provider_config.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text},
                ],
                temperature=self.translation_config.temperature,
                max_output_tokens=self.translation_config.max_output_tokens or None,
            )
            usage = getattr(response, "usage", None)
            return ProviderResult(
                text=getattr(response, "output_text", "").strip(),
                prompt_tokens=getattr(usage, "input_tokens", 0) or 0,
                completion_tokens=getattr(usage, "output_tokens", 0) or 0,
            )

        response = client.chat.completions.create(
            model=self.provider_config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text},
            ],
            temperature=self.translation_config.temperature,
            max_tokens=self.translation_config.max_output_tokens or None,
        )
        usage = getattr(response, "usage", None)
        content = response.choices[0].message.content or ""
        return ProviderResult(
            text=content.strip(),
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )


def _parse_json_payload(payload: str) -> dict[str, Any] | None:
    """Try to parse *payload* as JSON, falling back to brace-extraction."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        start = payload.find("{")
        end = payload.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(payload[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _strip_markdown_fences(text: str) -> str:
    """Remove surrounding markdown code fences if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_nl = stripped.find("\n")
        if first_nl != -1:
            stripped = stripped[first_nl + 1:]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


class CodexCLIProvider(BaseProvider):
    max_empty_retries = 3

    def __init__(self, provider: ProviderConfig, translation: TranslationConfig) -> None:
        self.provider_config = provider
        self.translation_config = translation
        self.codex_command = shutil.which("codex")
        if self.codex_command is None:
            raise RuntimeError("Codex CLI was not found in PATH. Install Codex and run `codex login` first.")

    def translate(self, text: str, system_prompt: str, user_prompt: str | None = None) -> ProviderResult:
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as handle:
            output_path = Path(handle.name)
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as handle:
            schema_path = Path(handle.name)
        schema_path.write_text(json.dumps(self._output_schema(), indent=2), encoding="utf-8")

        prompt = self._build_structured_prompt(system_prompt, user_prompt or text)
        cmd = [
            self.codex_command,
            "exec",
            "-s",
            "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "--color",
            "never",
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
            "-",
        ]
        if self.provider_config.model:
            cmd[2:2] = ["-m", self.provider_config.model]
        if self.provider_config.reasoning_effort:
            cmd[2:2] = ["-c", f'model_reasoning_effort="{self.provider_config.reasoning_effort}"']

        try:
            last_error = ""
            for attempt in range(1, self.max_empty_retries + 1):
                output_path.write_text("", encoding="utf-8")
                completed = subprocess.run(
                    cmd,
                    input=prompt,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=self.provider_config.timeout_seconds,
                )
                raw_payload = output_path.read_text(encoding="utf-8", errors="ignore").strip()
                stdout = (completed.stdout or "").strip()
                stderr = (completed.stderr or "").strip()

                if completed.returncode != 0:
                    raise RuntimeError(
                        "Codex translation failed. Ensure `codex login` works in your shell. "
                        f"Exit code: {completed.returncode}. Details: {stderr[-1200:]}"
                    )

                translated_text = self._extract_translation(raw_payload, stdout)
                if translated_text:
                    return ProviderResult(text=translated_text)

                last_error = (
                    "Codex returned an empty structured translation. "
                    f"Attempt {attempt}/{self.max_empty_retries}. "
                    f"stdout: {stdout[-400:]} stderr: {stderr[-400:]}"
                )

            raise RuntimeError(last_error or "Codex returned an empty structured translation.")
        finally:
            output_path.unlink(missing_ok=True)
            schema_path.unlink(missing_ok=True)

    @staticmethod
    def _output_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "translation": {
                    "type": "string",
                    "description": "The translated text for the CURRENT_TEXT section only.",
                }
            },
            "required": ["translation"],
            "additionalProperties": False,
        }

    @staticmethod
    def _build_structured_prompt(system_prompt: str, user_prompt: str) -> str:
        return (
            f"{system_prompt}\n\n"
            f"{user_prompt}\n\n"
            "Return a JSON object that matches the provided schema. "
            "Set `translation` to the translated text only. "
            "Do not return markdown fences, explanations, or extra keys. "
            "If the source is difficult, still provide the best possible non-empty translation."
        )

    @staticmethod
    def _extract_translation(raw_payload: str, stdout: str) -> str:
        for candidate in (raw_payload, stdout):
            if not candidate:
                continue
            parsed = CodexCLIProvider._parse_json_payload(candidate)
            if parsed:
                translation = str(parsed.get("translation", "")).strip()
                if translation:
                    return translation
        return ""

    @staticmethod
    def _parse_json_payload(payload: str) -> dict[str, Any] | None:
        return _parse_json_payload(payload)


class ClaudeCodeCLIProvider(BaseProvider):
    """Translation provider using the Claude Code CLI (``claude``)."""

    max_empty_retries = 3

    def __init__(self, provider: ProviderConfig, translation: TranslationConfig) -> None:
        self.provider_config = provider
        self.translation_config = translation
        self.claude_command = shutil.which("claude")
        if self.claude_command is None:
            raise RuntimeError(
                "Claude Code CLI was not found in PATH. "
                "Install Claude Code (https://docs.anthropic.com/en/docs/claude-code) first."
            )

    def translate(self, text: str, system_prompt: str, user_prompt: str | None = None) -> ProviderResult:
        prompt = self._build_structured_prompt(system_prompt, user_prompt or text)
        cmd = [
            self.claude_command,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--max-turns",
            "1",
        ]
        if self.provider_config.model:
            cmd.extend(["--model", self.provider_config.model])

        last_error = ""
        for attempt in range(1, self.max_empty_retries + 1):
            completed = subprocess.run(
                cmd,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.provider_config.timeout_seconds,
            )
            stdout = (completed.stdout or "").strip()
            stderr = (completed.stderr or "").strip()

            if completed.returncode != 0:
                raise RuntimeError(
                    "Claude Code translation failed. "
                    f"Exit code: {completed.returncode}. Details: {stderr[-1200:]}"
                )

            translated_text = self._extract_translation(stdout)
            if translated_text:
                return ProviderResult(text=translated_text)

            last_error = (
                "Claude Code returned an empty translation. "
                f"Attempt {attempt}/{self.max_empty_retries}. "
                f"stdout: {stdout[-400:]} stderr: {stderr[-400:]}"
            )

        raise RuntimeError(last_error or "Claude Code returned an empty translation.")

    @staticmethod
    def _build_structured_prompt(system_prompt: str, user_prompt: str) -> str:
        return (
            f"{system_prompt}\n\n"
            f"{user_prompt}\n\n"
            "Return ONLY a JSON object with a single key `translation` containing "
            "the translated text. Do not return markdown fences, explanations, or "
            'extra keys. Example: {"translation": "translated text here"}\n'
            "If the source is difficult, still provide the best possible non-empty translation."
        )

    @staticmethod
    def _extract_translation(stdout: str) -> str:
        if not stdout:
            return ""
        # Claude Code --output-format json returns an envelope with a "result" field
        envelope = _parse_json_payload(stdout)
        if envelope:
            if envelope.get("is_error"):
                return ""
            result = str(envelope.get("result", "")).strip()
            if result:
                # Try to parse result as JSON with "translation" key
                inner = _parse_json_payload(result)
                if inner:
                    translation = str(inner.get("translation", "")).strip()
                    if translation:
                        return translation
                # Fall back to raw result text (strip markdown fences)
                return _strip_markdown_fences(result)
            # Direct translation JSON (unlikely but handle it)
            translation = str(envelope.get("translation", "")).strip()
            if translation:
                return translation
        return ""


class GeminiCLIProvider(BaseProvider):
    """Translation provider using the Gemini CLI (``gemini``)."""

    max_empty_retries = 3

    def __init__(self, provider: ProviderConfig, translation: TranslationConfig) -> None:
        self.provider_config = provider
        self.translation_config = translation
        self.gemini_command = shutil.which("gemini")
        if self.gemini_command is None:
            raise RuntimeError(
                "Gemini CLI was not found in PATH. "
                "Install Gemini CLI (https://github.com/google-gemini/gemini-cli) first."
            )

    def translate(self, text: str, system_prompt: str, user_prompt: str | None = None) -> ProviderResult:
        prompt = self._build_structured_prompt(system_prompt, user_prompt or text)
        cmd = [
            self.gemini_command,
            "-p",
            prompt,
            "-o",
            "json",
        ]
        if self.provider_config.model:
            cmd.extend(["-m", self.provider_config.model])

        last_error = ""
        for attempt in range(1, self.max_empty_retries + 1):
            completed = subprocess.run(
                cmd,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.provider_config.timeout_seconds,
            )
            stdout = (completed.stdout or "").strip()
            stderr = (completed.stderr or "").strip()

            if completed.returncode != 0:
                raise RuntimeError(
                    "Gemini CLI translation failed. "
                    f"Exit code: {completed.returncode}. Details: {stderr[-1200:]}"
                )

            translated_text = self._extract_translation(stdout)
            if translated_text:
                return ProviderResult(text=translated_text)

            last_error = (
                "Gemini CLI returned an empty translation. "
                f"Attempt {attempt}/{self.max_empty_retries}. "
                f"stdout: {stdout[-400:]} stderr: {stderr[-400:]}"
            )

        raise RuntimeError(last_error or "Gemini CLI returned an empty translation.")

    @staticmethod
    def _build_structured_prompt(system_prompt: str, user_prompt: str) -> str:
        return (
            f"{system_prompt}\n\n"
            f"{user_prompt}\n\n"
            "Return ONLY a JSON object with a single key `translation` containing "
            "the translated text. Do not return markdown fences, explanations, or "
            'extra keys. Example: {"translation": "translated text here"}\n'
            "If the source is difficult, still provide the best possible non-empty translation."
        )

    @staticmethod
    def _extract_translation(stdout: str) -> str:
        if not stdout:
            return ""
        # Gemini -o json returns an envelope with a "response" field
        envelope = _parse_json_payload(stdout)
        if envelope:
            response = str(envelope.get("response", "")).strip()
            if response:
                # Try to parse response as JSON with "translation" key
                inner = _parse_json_payload(response)
                if inner:
                    translation = str(inner.get("translation", "")).strip()
                    if translation:
                        return translation
                # Fall back to raw response text (strip markdown fences)
                return _strip_markdown_fences(response)
            # Direct translation JSON
            translation = str(envelope.get("translation", "")).strip()
            if translation:
                return translation
        return ""


def build_provider(provider: ProviderConfig, translation: TranslationConfig) -> BaseProvider:
    if provider.kind == "mock":
        return MockProvider(translation)
    if provider.kind == "codex":
        return CodexCLIProvider(provider, translation)
    if provider.kind == "claude":
        return ClaudeCodeCLIProvider(provider, translation)
    if provider.kind == "gemini":
        return GeminiCLIProvider(provider, translation)
    return OpenAICompatibleProvider(provider, translation)
