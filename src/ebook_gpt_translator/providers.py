from __future__ import annotations

import itertools
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


class CodexCLIProvider(BaseProvider):
    def __init__(self, provider: ProviderConfig, translation: TranslationConfig) -> None:
        self.provider_config = provider
        self.translation_config = translation
        self.codex_command = shutil.which("codex")
        if self.codex_command is None:
            raise RuntimeError("Codex CLI was not found in PATH. Install Codex and run `codex login` first.")

    def translate(self, text: str, system_prompt: str, user_prompt: str | None = None) -> ProviderResult:
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as handle:
            output_path = Path(handle.name)

        prompt = f"{system_prompt}\n\n{user_prompt or text}"
        cmd = [
            self.codex_command,
            "exec",
            "-s",
            "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "--color",
            "never",
            "-o",
            str(output_path),
            "-",
        ]
        if self.provider_config.model:
            cmd[2:2] = ["-m", self.provider_config.model]
        if self.provider_config.reasoning_effort:
            cmd[2:2] = ["-c", f'model_reasoning_effort="{self.provider_config.reasoning_effort}"']

        try:
            completed = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.provider_config.timeout_seconds,
            )
        finally:
            translated_text = output_path.read_text(encoding="utf-8", errors="ignore").strip()
            output_path.unlink(missing_ok=True)

        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            raise RuntimeError(
                "Codex translation failed. Ensure `codex login` works in your shell. "
                f"Exit code: {completed.returncode}. Details: {stderr[-1200:]}"
            )
        if not translated_text:
            raise RuntimeError("Codex returned an empty translation.")
        return ProviderResult(text=translated_text)


def build_provider(provider: ProviderConfig, translation: TranslationConfig) -> BaseProvider:
    if provider.kind == "mock":
        return MockProvider(translation)
    if provider.kind == "codex":
        return CodexCLIProvider(provider, translation)
    return OpenAICompatibleProvider(provider, translation)
