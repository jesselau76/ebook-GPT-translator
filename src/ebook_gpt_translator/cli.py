from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console

from ebook_gpt_translator.config import AppConfig, apply_cli_overrides, ensure_runtime_paths, load_config
from ebook_gpt_translator.pipeline import translate_file


app = typer.Typer(add_completion=False, help="Translate ebooks with modern OpenAI-compatible APIs.")
auth_app = typer.Typer(add_completion=False, help="Manage local provider credentials.")
console = Console()
app.add_typer(auth_app, name="auth")


@app.command()
def translate(
    input_path: Path = typer.Argument(..., exists=True, readable=True, help="Source ebook or text file."),
    config_path: str = typer.Option("", "--config", "-c", help="Path to settings.toml or legacy settings.cfg."),
    env_file: str = typer.Option("", "--env-file", help="Optional .env file."),
    provider: str = typer.Option(None, "--provider", help="codex, claude, gemini, openai, azure, compatible, or mock."),
    model: str = typer.Option(None, "--model", help="Model, Codex model slug, or Azure deployment name."),
    reasoning_effort: str = typer.Option(
        None,
        "--reasoning-effort",
        help="Codex reasoning effort, e.g. minimal, low, medium, high, xhigh.",
    ),
    api_key: str = typer.Option(None, "--api-key", help="API key or comma-separated key ring."),
    api_base_url: str = typer.Option(None, "--api-base-url", help="Custom base URL or Azure endpoint."),
    api_version: str = typer.Option(None, "--api-version", help="Azure API version."),
    api_mode: str = typer.Option(None, "--api-mode", help="auto, responses, or chat."),
    target_language: str = typer.Option(None, "--target-language", help="Target language."),
    context_window: int = typer.Option(
        None,
        "--context-window",
        help="How many previous translated blocks to include for consistency.",
    ),
    glossary_path: str = typer.Option(None, "--glossary", help="Glossary CSV path."),
    bilingual: bool = typer.Option(None, "--bilingual/--no-bilingual", help="Write bilingual output."),
    dry_run: bool = typer.Option(None, "--dry-run", help="Skip API calls and emit placeholder translations."),
    test_mode: bool = typer.Option(None, "--test", help="Translate only the first few text blocks."),
    test_limit: int = typer.Option(None, "--test-limit", help="Block limit when --test is used."),
    max_chars: int = typer.Option(None, "--max-chars", help="Maximum characters per chunk."),
    max_tokens: int = typer.Option(None, "--max-tokens", help="Maximum tokens per chunk."),
    start_page: int = typer.Option(None, "--start-page", help="Start page for PDF input."),
    end_page: int = typer.Option(None, "--end-page", help="End page for PDF input."),
    output_dir: str = typer.Option(None, "--output-dir", help="Directory for generated files."),
    txt_only: bool = typer.Option(False, "--txt-only", help="Write only TXT output."),
    epub_only: bool = typer.Option(False, "--epub-only", help="Write only EPUB output."),
    skip_existing: bool = typer.Option(None, "--skip-existing", help="Skip if translated outputs already exist."),
    overwrite: bool = typer.Option(None, "--overwrite", help="Overwrite existing translated outputs."),
) -> None:
    config = load_config(config_path or None, env_file or None)
    overrides = {
        "provider.kind": provider,
        "provider.model": model,
        "provider.reasoning_effort": reasoning_effort,
        "provider.api_key": api_key,
        "provider.api_base_url": api_base_url,
        "provider.api_version": api_version,
        "provider.api_mode": api_mode,
        "translation.target_language": target_language,
        "translation.context_window_blocks": context_window,
        "translation.bilingual_output": bilingual,
        "glossary.path": glossary_path,
        "runtime.dry_run": dry_run,
        "runtime.test_mode": test_mode,
        "chunking.test_limit": test_limit,
        "chunking.max_chars": max_chars,
        "chunking.max_tokens": max_tokens,
        "input.start_page": start_page,
        "input.end_page": end_page,
        "output.output_dir": output_dir,
        "output.skip_existing": skip_existing,
        "output.overwrite": overwrite,
    }
    config = apply_cli_overrides(config, overrides)
    if txt_only:
        config.output.emit_epub = False
        config.output.emit_txt = True
    if epub_only:
        config.output.emit_txt = False
        config.output.emit_epub = True

    ensure_runtime_paths(config)
    if _should_skip(input_path, config):
        console.print(f"[yellow]Skipping[/yellow] {input_path} because translated outputs already exist.")
        return

    _, artifacts, stats = translate_file(input_path, config)
    _print_summary(artifacts, stats, config)


@app.command("init-config")
def init_config(
    destination: Path = typer.Argument(Path("settings.toml"), help="Path to write the example config."),
    legacy: bool = typer.Option(False, "--legacy", help="Write the legacy settings.cfg.example format."),
) -> None:
    content = LEGACY_CONFIG_EXAMPLE if legacy else TOML_CONFIG_EXAMPLE
    destination.write_text(content, encoding="utf-8")
    console.print(f"Wrote config template to {destination}")


@app.command("list-models")
def list_models(
    source: str = typer.Option(
        "codex",
        "--source",
        help="Model catalog source: codex, claude, or gemini.",
    ),
    show_all: bool = typer.Option(False, "--all", help="Show all visible models."),
) -> None:
    if source == "claude":
        models = _load_claude_models()
        if not models:
            console.print("No Claude Code models available.")
            raise typer.Exit(1)
        for model in models:
            console.print(model)
        return

    if source == "gemini":
        models = _load_gemini_models()
        if not models:
            console.print("No Gemini models available.")
            raise typer.Exit(1)
        for model in models:
            console.print(model)
        return

    if source != "codex":
        raise typer.BadParameter("source must be one of: codex, claude, gemini")

    models = _load_codex_models()
    if not models:
        console.print("No Codex model cache found. Run `codex login` first.")
        raise typer.Exit(1)

    for model in models:
        slug = model.get("slug", "")
        visibility = model.get("visibility", "")
        if not show_all and visibility not in {"list", "default", ""}:
            continue
        default_effort = model.get("default_reasoning_level", "")
        efforts = [item.get("effort", "") for item in model.get("supported_reasoning_levels", [])]
        description = model.get("description", "")
        effort_text = ", ".join(effort for effort in efforts if effort)
        console.print(f"{slug}")
        console.print(f"  default effort: {default_effort or '(unset)'}")
        console.print(f"  supported efforts: {effort_text or '(none)'}")
        if description:
            console.print(f"  {description}")


@auth_app.command("login")
def auth_login(
    env_file: Path = typer.Option(Path(".env"), "--env-file", help="Where to store credentials."),
    provider: str = typer.Option("openai", "--provider", help="codex, claude, gemini, openai, azure, or compatible."),
    api_key: str = typer.Option("", "--api-key", help="API key. Prompted if omitted."),
    api_base_url: str = typer.Option("", "--api-base-url", help="Custom base URL or Azure endpoint."),
    api_version: str = typer.Option("", "--api-version", help="Azure API version."),
    model: str = typer.Option("", "--model", help="Default model or deployment name."),
    reasoning_effort: str = typer.Option(
        "",
        "--reasoning-effort",
        help="Default Codex reasoning effort, e.g. low, medium, high.",
    ),
    target_language: str = typer.Option("", "--target-language", help="Optional default target language."),
) -> None:
    normalized_provider = provider.strip().lower()
    if normalized_provider not in {"codex", "claude", "gemini", "openai", "azure", "compatible"}:
        raise typer.BadParameter("provider must be one of: codex, claude, gemini, openai, azure, compatible")

    if normalized_provider in {"codex", "claude", "gemini"}:
        if normalized_provider == "codex":
            _run_codex_command(["login"])
        elif normalized_provider == "claude":
            _run_claude_command([])
        elif normalized_provider == "gemini":
            _run_gemini_command(["auth", "login"])
        values = _read_env_file(env_file)
        values["EBOOK_TRANSLATOR_PROVIDER"] = normalized_provider
        values.pop("EBOOK_TRANSLATOR_API_KEY", None)
        values.pop("EBOOK_TRANSLATOR_API_BASE_URL", None)
        values.pop("EBOOK_TRANSLATOR_API_VERSION", None)
        if model:
            values["EBOOK_TRANSLATOR_MODEL"] = model.strip()
        else:
            values.pop("EBOOK_TRANSLATOR_MODEL", None)
        if reasoning_effort:
            values["EBOOK_TRANSLATOR_REASONING_EFFORT"] = reasoning_effort.strip()
        else:
            values.pop("EBOOK_TRANSLATOR_REASONING_EFFORT", None)
        if target_language:
            values["EBOOK_TRANSLATOR_TARGET_LANGUAGE"] = target_language.strip()
        _write_env_values(env_file, values)
        console.print(f"Saved provider selection to {env_file}")
        console.print(f"{normalized_provider.capitalize()} login completed. You can now translate with --provider {normalized_provider}.")
        return

    if not api_key:
        api_key = typer.prompt("OpenAI API key", hide_input=True).strip()
    if not api_key:
        raise typer.BadParameter("An API key is required.")

    updates = {
        "EBOOK_TRANSLATOR_PROVIDER": normalized_provider,
        "EBOOK_TRANSLATOR_API_KEY": api_key,
    }
    if api_base_url:
        updates["EBOOK_TRANSLATOR_API_BASE_URL"] = api_base_url.strip()
    if api_version:
        updates["EBOOK_TRANSLATOR_API_VERSION"] = api_version.strip()
    if model:
        updates["EBOOK_TRANSLATOR_MODEL"] = model.strip()
    if target_language:
        updates["EBOOK_TRANSLATOR_TARGET_LANGUAGE"] = target_language.strip()

    _write_env_updates(env_file, updates)
    console.print(f"Saved credentials to {env_file}")
    console.print("You can now run: PYTHONPATH=src python3 -m ebook_gpt_translator translate <file>")


@auth_app.command("status")
def auth_status(
    env_file: Path = typer.Option(Path(".env"), "--env-file", help="Credential file to inspect."),
) -> None:
    values = _read_env_file(env_file)
    if not env_file.exists():
        console.print(f"No env file found at {env_file}")
    provider = values.get("EBOOK_TRANSLATOR_PROVIDER", "")
    key = values.get("EBOOK_TRANSLATOR_API_KEY", "")
    base_url = values.get("EBOOK_TRANSLATOR_API_BASE_URL", "")
    console.print(f"Env file: {env_file}")
    console.print(f"Provider: {provider or '(unset)'}")
    console.print(f"Model: {values.get('EBOOK_TRANSLATOR_MODEL', '(unset)')}")
    console.print(f"Reasoning effort: {values.get('EBOOK_TRANSLATOR_REASONING_EFFORT', '(unset)')}")
    console.print(f"Context window: {values.get('EBOOK_TRANSLATOR_CONTEXT_WINDOW_BLOCKS', '(unset)')}")
    console.print(f"API key: {_mask_secret(key) if key else '(unset)'}")
    console.print(f"API base URL: {base_url or '(unset)'}")
    codex_path = shutil.which("codex")
    if codex_path:
        completed = subprocess.run(
            [codex_path, "login", "status"],
            text=True, capture_output=True, check=False,
        )
        status_text = (completed.stdout or completed.stderr).strip()
        console.print(f"Codex CLI: {status_text or 'status unavailable'}")
    else:
        console.print("Codex CLI: not found")
    claude_path = shutil.which("claude")
    if claude_path:
        console.print("Claude Code CLI: installed")
    else:
        console.print("Claude Code CLI: not found")
    gemini_path = shutil.which("gemini")
    if gemini_path:
        completed = subprocess.run(
            [gemini_path, "--version"],
            text=True, capture_output=True, check=False, timeout=10,
        )
        version = (completed.stdout or "").strip()
        console.print(f"Gemini CLI: installed ({version})" if version else "Gemini CLI: installed")
    else:
        console.print("Gemini CLI: not found")


@auth_app.command("logout")
def auth_logout(
    env_file: Path = typer.Option(Path(".env"), "--env-file", help="Credential file to update."),
    provider: str = typer.Option("", "--provider", help="Optional provider to log out, e.g. codex."),
) -> None:
    normalized_provider = provider.strip().lower()
    if normalized_provider == "codex":
        _run_codex_command(["logout"])
    elif normalized_provider == "gemini":
        _run_gemini_command(["auth", "logout"])

    keys = {
        "EBOOK_TRANSLATOR_PROVIDER",
        "EBOOK_TRANSLATOR_API_KEY",
        "EBOOK_TRANSLATOR_API_BASE_URL",
        "EBOOK_TRANSLATOR_API_VERSION",
        "EBOOK_TRANSLATOR_MODEL",
        "EBOOK_TRANSLATOR_REASONING_EFFORT",
        "EBOOK_TRANSLATOR_TARGET_LANGUAGE",
        "EBOOK_TRANSLATOR_CONTEXT_WINDOW_BLOCKS",
    }
    values = _read_env_file(env_file)
    if not values:
        console.print(f"No credentials found in {env_file}")
        return
    for key in keys:
        values.pop(key, None)
    _write_env_values(env_file, values)
    console.print(f"Removed saved credentials from {env_file}")


def _should_skip(input_path: Path, config: AppConfig) -> bool:
    if not config.output.skip_existing or config.output.overwrite:
        return False
    base = Path(config.output.output_dir) / input_path.stem
    expected = []
    if config.output.emit_txt:
        expected.append(base.with_name(f"{base.name}.translated.txt"))
    if config.output.emit_epub:
        expected.append(base.with_name(f"{base.name}.translated.epub"))
    return expected and all(path.exists() for path in expected)


def _print_summary(artifacts, stats, config: AppConfig) -> None:
    console.print("Translation complete.")
    if artifacts.text_path:
        console.print(f"TXT: {artifacts.text_path}")
    if artifacts.epub_path:
        console.print(f"EPUB: {artifacts.epub_path}")
    if artifacts.manifest_path:
        console.print(f"Manifest: {artifacts.manifest_path}")
    if artifacts.memory_path:
        console.print(f"Memory: {artifacts.memory_path}")
    console.print(
        f"Blocks: {stats.translated_blocks} | API calls: {stats.api_calls} | "
        f"Cache hits: {stats.cache_hits} | Prompt tokens: {stats.prompt_tokens} | "
        f"Completion tokens: {stats.completion_tokens}"
    )
    if config.runtime.dry_run:
        console.print("Dry run mode was enabled.")


def _read_env_file(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        return {}
    values: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env_updates(env_file: Path, updates: dict[str, str]) -> None:
    values = _read_env_file(env_file)
    values.update({key: value for key, value in updates.items() if value != ""})
    _write_env_values(env_file, values)


def _write_env_values(env_file: Path, values: dict[str, str]) -> None:
    env_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in sorted(values.items())]
    env_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _run_codex_command(args: list[str]) -> None:
    codex_path = shutil.which("codex")
    if codex_path is None:
        raise typer.BadParameter("Codex CLI was not found in PATH.")
    completed = subprocess.run([codex_path, *args], check=False)
    if completed.returncode != 0:
        raise typer.Exit(completed.returncode)


def _run_claude_command(args: list[str]) -> None:
    claude_path = shutil.which("claude")
    if claude_path is None:
        raise typer.BadParameter("Claude Code CLI was not found in PATH.")
    completed = subprocess.run([claude_path, *args], check=False)
    if completed.returncode != 0:
        raise typer.Exit(completed.returncode)


def _run_gemini_command(args: list[str]) -> None:
    gemini_path = shutil.which("gemini")
    if gemini_path is None:
        raise typer.BadParameter("Gemini CLI was not found in PATH.")
    completed = subprocess.run([gemini_path, *args], check=False)
    if completed.returncode != 0:
        raise typer.Exit(completed.returncode)


def _load_codex_models() -> list[dict]:
    cache_path = Path.home() / ".codex" / "models_cache.json"
    if not cache_path.exists():
        return []
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    return data.get("models", [])


def _load_claude_models() -> list[str]:
    return ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"]


def _load_gemini_models() -> list[str]:
    return [
        "gemini-3-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]


TOML_CONFIG_EXAMPLE = """[provider]
# kind: codex, claude, gemini, openai, azure, compatible, or mock
kind = "codex"
# model examples: gpt-5.2-codex (codex), claude-sonnet-4-6 (claude), gemini-3-pro-preview (gemini)
model = "gpt-5.2-codex"
reasoning_effort = "medium"
api_key = ""
api_base_url = ""
api_version = ""
api_mode = "auto"
timeout_seconds = 120
max_retries = 5
proxy = ""

[translation]
target_language = "Simplified Chinese"
bilingual_output = false
custom_prompt = ""
temperature = 0.2
max_output_tokens = 0
preserve_line_breaks = true
context_window_blocks = 4

[chunking]
max_chars = 1800
max_tokens = 1200
test_limit = 3

[input]
start_page = 1
end_page = -1

[glossary]
path = ""
case_sensitive = false

[output]
output_dir = "output"
emit_txt = true
emit_epub = true
skip_existing = false
overwrite = false
write_manifest = true

[runtime]
dry_run = false
test_mode = false
cache_path = ".cache/translation.sqlite3"
job_dir = ".cache/jobs"
"""


LEGACY_CONFIG_EXAMPLE = """[option]
provider = codex
model = gpt-5.2-codex
reasoning-effort = medium
openai-apikey =
openai-api-base =
api_version =
api_mode = auto
language = Simplified Chinese
bilingual-output = false
prompt = Please translate the following text into Simplified Chinese.
context-window-blocks = 4
max_len = 1800
max_token = 1200
startpage = 1
endpage = -1
transliteration-list = transliteration-list-example.xlsx
case-matching = false
output_dir = output
openai-proxy =
"""
