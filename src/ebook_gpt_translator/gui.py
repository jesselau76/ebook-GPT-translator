from __future__ import annotations

import json
import shutil
import subprocess
import threading
import traceback
from dataclasses import asdict
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ebook_gpt_translator.config import AppConfig, apply_cli_overrides, ensure_runtime_paths, load_config
from ebook_gpt_translator.pipeline import inspect_resume_state, translate_file


SUPPORTED_INPUTS = [
    ("Books and Text", "*.epub *.pdf *.docx *.txt *.md *.mobi"),
    ("EPUB", "*.epub"),
    ("PDF", "*.pdf"),
    ("DOCX", "*.docx"),
    ("Text", "*.txt *.md"),
    ("MOBI", "*.mobi"),
    ("All files", "*.*"),
]

COMMON_LANGUAGES = [
    "Simplified Chinese",
    "Traditional Chinese",
    "English",
    "Japanese",
    "Korean",
    "French",
    "German",
    "Spanish",
    "Italian",
    "Russian",
    "Portuguese",
    "Arabic",
    "Thai",
    "Vietnamese",
]


def main() -> None:
    app = TranslatorGUI()
    app.run()


def build_config_from_form(form: dict[str, Any]) -> AppConfig:
    config = load_config(form.get("config_path") or None, form.get("env_file") or None)
    overrides = {
        "provider.kind": form.get("provider"),
        "provider.model": form.get("model"),
        "provider.reasoning_effort": form.get("reasoning_effort"),
        "provider.api_key": form.get("api_key"),
        "provider.api_base_url": form.get("api_base_url"),
        "provider.api_version": form.get("api_version"),
        "provider.api_mode": form.get("api_mode"),
        "translation.target_language": form.get("target_language"),
        "translation.custom_prompt": form.get("custom_prompt"),
        "translation.context_window_blocks": form.get("context_window"),
        "translation.bilingual_output": form.get("bilingual"),
        "glossary.path": form.get("glossary_path"),
        "runtime.dry_run": form.get("dry_run"),
        "runtime.test_mode": form.get("test_mode"),
        "chunking.test_limit": form.get("test_limit"),
        "chunking.max_chars": form.get("max_chars"),
        "chunking.max_tokens": form.get("max_tokens"),
        "input.start_page": form.get("start_page"),
        "input.end_page": form.get("end_page"),
        "output.output_dir": form.get("output_dir"),
        "output.skip_existing": form.get("skip_existing"),
        "output.overwrite": form.get("overwrite"),
    }
    config = apply_cli_overrides(config, overrides)
    if form.get("txt_only"):
        config.output.emit_epub = False
        config.output.emit_txt = True
    if form.get("epub_only"):
        config.output.emit_txt = False
        config.output.emit_epub = True
    ensure_runtime_paths(config)
    return config


CLAUDE_CODE_MODELS = ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"]
GEMINI_MODELS = [
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]


def load_codex_model_choices() -> list[str]:
    try:
        from ebook_gpt_translator.cli import _load_codex_models

        models = _load_codex_models()
    except Exception:
        return ["gpt-5.2-codex", "gpt-5.1-codex", "gpt-5-codex-mini"]

    slugs = [model.get("slug", "") for model in models if model.get("slug")]
    preferred = [slug for slug in slugs if "codex" in slug]
    fallback = [slug for slug in slugs if "codex" not in slug]
    return preferred + fallback or ["gpt-5.2-codex", "gpt-5.1-codex", "gpt-5-codex-mini"]


def load_claude_model_choices() -> list[str]:
    return list(CLAUDE_CODE_MODELS)


def load_gemini_model_choices() -> list[str]:
    return list(GEMINI_MODELS)


_CUSTOM_MODELS_PATH = Path(".cache/custom_models.json")

_DEFAULT_MODELS: dict[str, list[str]] = {
    "codex": [],   # loaded dynamically
    "claude": list(CLAUDE_CODE_MODELS),
    "gemini": list(GEMINI_MODELS),
}


def _load_custom_models() -> dict[str, list[str]]:
    if not _CUSTOM_MODELS_PATH.exists():
        return {}
    try:
        data = json.loads(_CUSTOM_MODELS_PATH.read_text(encoding="utf-8"))
        return {k: list(v) for k, v in data.items() if isinstance(v, list)}
    except Exception:
        return {}


def _save_custom_models(custom: dict[str, list[str]]) -> None:
    _CUSTOM_MODELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CUSTOM_MODELS_PATH.write_text(json.dumps(custom, indent=2, ensure_ascii=False), encoding="utf-8")


class TranslatorGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("ebook-GPT-translator")
        self.root.geometry("980x760")
        self.root.minsize(900, 680)

        self.queue: Queue[tuple[str, Any]] = Queue()
        self.worker: threading.Thread | None = None
        self.custom_models = _load_custom_models()
        self.codex_model_choices = load_codex_model_choices()
        self.claude_model_choices = load_claude_model_choices()
        self.gemini_model_choices = load_gemini_model_choices()

        self.file_path = tk.StringVar()
        self.config_path = tk.StringVar()
        self.env_file = tk.StringVar(value=".env")
        self.output_dir = tk.StringVar(value="output")
        self.glossary_path = tk.StringVar()
        self.provider = tk.StringVar(value="codex")
        self.model = tk.StringVar(value="gpt-5.2-codex")
        self.reasoning_effort = tk.StringVar(value="medium")
        self.target_language = tk.StringVar(value="Simplified Chinese")
        self.custom_prompt = tk.StringVar()
        self.api_key = tk.StringVar()
        self.api_base_url = tk.StringVar()
        self.api_version = tk.StringVar()
        self.api_mode = tk.StringVar(value="auto")
        self.context_window = tk.IntVar(value=6)
        self.max_chars = tk.IntVar(value=5000)
        self.max_tokens = tk.IntVar(value=3500)
        self.test_limit = tk.IntVar(value=3)
        self.start_page = tk.IntVar(value=1)
        self.end_page = tk.IntVar(value=-1)
        self.bilingual = tk.BooleanVar(value=False)
        self.dry_run = tk.BooleanVar(value=False)
        self.test_mode = tk.BooleanVar(value=False)
        self.txt_only = tk.BooleanVar(value=False)
        self.epub_only = tk.BooleanVar(value=False)
        self.skip_existing = tk.BooleanVar(value=False)
        self.overwrite = tk.BooleanVar(value=False)
        self.force_resume = tk.BooleanVar(value=False)
        self.status_text = tk.StringVar(value="Idle")
        self.progress_value = tk.DoubleVar(value=0.0)
        self.progress_detail = tk.StringVar(value="No active translation.")
        self.resume_status = tk.StringVar(value="Resume status unavailable.")
        self.codex_status = tk.StringVar(value=self._get_cli_status("codex"))
        self.claude_status = tk.StringVar(value=self._get_cli_status("claude"))
        self.gemini_status = tk.StringVar(value=self._get_cli_status("gemini"))

        self._build_layout()
        self.root.after(150, self._process_queue)

    def run(self) -> None:
        self.root.mainloop()

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        header = ttk.Frame(self.root, padding=12)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="ebook-GPT-translator", font=("TkDefaultFont", 16, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(header, textvariable=self.status_text, foreground="#1f4f82").grid(
            row=0, column=1, sticky="e"
        )
        progress_frame = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        progress_frame.grid(row=1, column=0, sticky="ew")
        progress_frame.columnconfigure(0, weight=1)
        ttk.Progressbar(progress_frame, variable=self.progress_value, maximum=100).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Label(progress_frame, textvariable=self.progress_detail, foreground="#4a4a4a").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )

        body = ttk.Panedwindow(self.root, orient=tk.VERTICAL)
        body.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))

        form_container = ttk.Frame(body, padding=8)
        log_container = ttk.Frame(body, padding=8)
        body.add(form_container, weight=3)
        body.add(log_container, weight=2)

        self._build_form(form_container)
        self._build_log(log_container)

    def _build_form(self, parent: ttk.Frame) -> None:
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, padding=(0, 0, 10, 0))

        frame.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        row = 0
        row = self._file_field(frame, row, "Input file", self.file_path, self._choose_input)
        row = self._file_field(frame, row, "Config file", self.config_path, self._choose_config)
        row = self._file_field(frame, row, "Env file", self.env_file, self._choose_env)
        row = self._file_field(frame, row, "Output dir", self.output_dir, self._choose_output_dir, directory=True)
        row = self._file_field(frame, row, "Glossary", self.glossary_path, self._choose_glossary)

        ttk.Separator(frame).grid(row=row, column=0, columnspan=4, sticky="ew", pady=10)
        row += 1

        row = self._combo_field(
            frame,
            row,
            "Provider",
            self.provider,
            ["codex", "claude", "gemini", "openai", "azure", "compatible", "mock"],
            on_select=lambda _event: self._on_provider_changed(),
        )
        row = self._model_field(frame, row)
        row = self._combo_field(
            frame,
            row,
            "Reasoning effort",
            self.reasoning_effort,
            ["minimal", "low", "medium", "high", "xhigh"],
        )
        row = self._combo_field(frame, row, "Target language", self.target_language, COMMON_LANGUAGES)
        row = self._text_field(
            frame,
            row,
            "Custom prompt",
            "Optional style or instruction, e.g. use Dream of the Red Chamber style Chinese.",
        )
        row = self._entry_field(frame, row, "API key", self.api_key, show="*")
        row = self._entry_field(frame, row, "API base URL", self.api_base_url)
        row = self._entry_field(frame, row, "API version", self.api_version)
        row = self._combo_field(frame, row, "API mode", self.api_mode, ["auto", "responses", "chat"])

        ttk.Separator(frame).grid(row=row, column=0, columnspan=4, sticky="ew", pady=10)
        row += 1

        row = self._spin_field(frame, row, "Context window", self.context_window, from_=0, to=20)
        row = self._spin_field(frame, row, "Max chars", self.max_chars, from_=200, to=8000, increment=100)
        row = self._spin_field(frame, row, "Max tokens", self.max_tokens, from_=100, to=8000, increment=100)
        row = self._spin_field(frame, row, "Test limit", self.test_limit, from_=1, to=50)
        row = self._spin_field(frame, row, "PDF start page", self.start_page, from_=1, to=100000)
        row = self._spin_field(frame, row, "PDF end page", self.end_page, from_=-1, to=100000)

        ttk.Separator(frame).grid(row=row, column=0, columnspan=4, sticky="ew", pady=10)
        row += 1

        options = ttk.LabelFrame(frame, text="Options", padding=10)
        options.grid(row=row, column=0, columnspan=4, sticky="ew")
        for index in range(4):
            options.columnconfigure(index, weight=1)
        ttk.Checkbutton(options, text="Bilingual output", variable=self.bilingual).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(options, text="Dry run", variable=self.dry_run).grid(row=0, column=1, sticky="w")
        ttk.Checkbutton(options, text="Test mode", variable=self.test_mode).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(options, text="TXT only", variable=self.txt_only).grid(row=0, column=3, sticky="w")
        ttk.Checkbutton(options, text="EPUB only", variable=self.epub_only).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(options, text="Skip existing", variable=self.skip_existing).grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(options, text="Overwrite", variable=self.overwrite).grid(row=1, column=2, sticky="w")

        row += 1
        resume_box = ttk.LabelFrame(frame, text="Resume", padding=10)
        resume_box.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        resume_box.columnconfigure(0, weight=1)
        ttk.Label(resume_box, textvariable=self.resume_status, foreground="#4a4a4a", wraplength=760).grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Button(resume_box, text="Check resume", command=lambda: self._refresh_resume_status(log_message=True)).grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Checkbutton(resume_box, text="Force (ignore param changes)", variable=self.force_resume).grid(
            row=1, column=1, sticky="w", pady=(8, 0), padx=(8, 0)
        )
        ttk.Button(resume_box, text="Resume previous job", command=lambda: self._start_translation(resume_only=True)).grid(
            row=1, column=2, sticky="e", pady=(8, 0)
        )

        row += 1
        cli_box = ttk.LabelFrame(frame, text="CLI Tools", padding=10)
        cli_box.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        cli_box.columnconfigure(1, weight=1)
        ttk.Label(cli_box, text="Codex").grid(row=0, column=0, sticky="w")
        ttk.Label(cli_box, textvariable=self.codex_status).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Button(cli_box, text="Login", command=self._run_codex_login).grid(row=0, column=2, padx=4)
        ttk.Label(cli_box, text="Claude").grid(row=1, column=0, sticky="w")
        ttk.Label(cli_box, textvariable=self.claude_status).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Button(cli_box, text="Login", command=self._run_claude_login).grid(row=1, column=2, padx=4)
        ttk.Label(cli_box, text="Gemini").grid(row=2, column=0, sticky="w")
        ttk.Label(cli_box, textvariable=self.gemini_status).grid(row=2, column=1, sticky="w", padx=4)
        ttk.Button(cli_box, text="Login", command=self._run_gemini_login).grid(row=2, column=2, padx=4)
        ttk.Button(cli_box, text="Refresh", command=self._refresh_cli_status).grid(row=3, column=0, padx=4, pady=(6, 0))
        ttk.Button(cli_box, text="List models", command=self._list_models).grid(row=3, column=1, sticky="w", padx=4, pady=(6, 0))

        row += 1
        actions = ttk.Frame(frame, padding=(0, 12, 0, 0))
        actions.grid(row=row, column=0, columnspan=4, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)
        ttk.Button(actions, text="Save example config", command=self._save_example_config).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(actions, text="Start translation", command=self._start_translation).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Button(actions, text="Open output dir", command=self._open_output_dir).grid(
            row=0, column=2, sticky="ew", padx=(6, 0)
        )

    def _build_log(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        ttk.Label(parent, text="Run log", font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.log_widget = tk.Text(parent, wrap="word", height=18)
        self.log_widget.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.log_widget.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(8, 0))
        self.log_widget.configure(yscrollcommand=scrollbar.set, state="disabled")

    def _file_field(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        command,
        directory: bool = False,
    ) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Button(parent, text="Browse", command=command).grid(row=row, column=3, sticky="e", pady=4)
        _ = directory
        return row + 1

    def _entry_field(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        show: str | None = None,
    ) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        entry = ttk.Entry(parent, textvariable=variable, show=show or "")
        entry.grid(row=row, column=1, columnspan=3, sticky="ew", pady=4)
        return row + 1

    def _text_field(self, parent: ttk.Frame, row: int, label: str, hint: str) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="nw", pady=4, padx=(0, 8))
        box = tk.Text(parent, wrap="word", height=4)
        box.grid(row=row, column=1, columnspan=3, sticky="ew", pady=4)
        if self.custom_prompt.get():
            box.insert("1.0", self.custom_prompt.get())
        self.custom_prompt_box = box
        ttk.Label(parent, text=hint, foreground="#666666").grid(
            row=row + 1, column=1, columnspan=3, sticky="w", pady=(0, 6)
        )
        return row + 2

    def _combo_field(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        on_select=None,
    ) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        combo = ttk.Combobox(parent, textvariable=variable, values=values)
        combo.grid(row=row, column=1, columnspan=3, sticky="ew", pady=4)
        if on_select:
            combo.bind("<<ComboboxSelected>>", on_select)
        if label == "Model":
            self.model_combo = combo
        return row + 1

    def _model_field(self, parent: ttk.Frame, row: int) -> int:
        ttk.Label(parent, text="Model").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        choices = self._get_model_choices(self.provider.get())
        self.model_combo = ttk.Combobox(parent, textvariable=self.model, values=choices)
        self.model_combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=row, column=3, sticky="w", pady=4, padx=(4, 0))
        ttk.Button(btn_frame, text="+", width=3, command=self._add_custom_model).grid(row=0, column=0)
        ttk.Button(btn_frame, text="\u2212", width=3, command=self._remove_custom_model).grid(row=0, column=1, padx=(2, 0))
        # Hint row
        ttk.Label(parent, text="Type a model name and click + to add, or \u2212 to remove custom models",
                  foreground="#666666").grid(row=row + 1, column=1, columnspan=3, sticky="w", pady=(0, 4))
        return row + 2

    def _get_model_choices(self, provider: str) -> list[str]:
        provider = provider.strip().lower()
        if provider == "codex":
            defaults = self.codex_model_choices
        elif provider == "claude":
            defaults = self.claude_model_choices
        elif provider == "gemini":
            defaults = self.gemini_model_choices
        elif provider == "mock":
            return ["gpt-5.2-codex"]
        else:
            defaults = [self.model.get() or ""]
        custom = self.custom_models.get(provider, [])
        combined = list(defaults)
        for m in custom:
            if m and m not in combined:
                combined.append(m)
        return combined

    def _add_custom_model(self) -> None:
        model = self.model.get().strip()
        if not model:
            return
        provider = self.provider.get().strip().lower()
        existing = self._get_model_choices(provider)
        if model in existing:
            self._append_log(f"Model '{model}' already in list.")
            return
        custom = self.custom_models.setdefault(provider, [])
        custom.append(model)
        _save_custom_models(self.custom_models)
        self.model_combo.configure(values=self._get_model_choices(provider))
        self._append_log(f"Added custom model '{model}' for {provider}.")

    def _remove_custom_model(self) -> None:
        model = self.model.get().strip()
        if not model:
            return
        provider = self.provider.get().strip().lower()
        custom = self.custom_models.get(provider, [])
        if model not in custom:
            self._append_log(f"'{model}' is a built-in model and cannot be removed.")
            return
        custom.remove(model)
        _save_custom_models(self.custom_models)
        choices = self._get_model_choices(provider)
        self.model_combo.configure(values=choices)
        if choices:
            self.model.set(choices[0])
        self._append_log(f"Removed custom model '{model}' from {provider}.")

    def _spin_field(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.IntVar,
        from_: int,
        to: int,
        increment: int = 1,
    ) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Spinbox(parent, textvariable=variable, from_=from_, to=to, increment=increment).grid(
            row=row, column=1, sticky="w", pady=4
        )
        return row + 1

    def _choose_input(self) -> None:
        path = filedialog.askopenfilename(filetypes=SUPPORTED_INPUTS)
        if path:
            self.file_path.set(path)
            self._refresh_resume_status()

    def _choose_config(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Config", "*.toml *.cfg"), ("All files", "*.*")])
        if path:
            self.config_path.set(path)
            self._load_config_into_form(path)
            self._refresh_resume_status()

    def _load_config_into_form(self, config_path: str) -> None:
        try:
            config = load_config(config_path, self.env_file.get().strip() or None)
        except Exception as exc:
            self._append_log(f"Failed to load config: {exc}")
            return
        p = config.provider
        t = config.translation
        c = config.chunking
        inp = config.input
        g = config.glossary
        o = config.output
        if p.kind:
            self.provider.set(p.kind)
        if p.model:
            self.model.set(p.model)
        if p.reasoning_effort:
            self.reasoning_effort.set(p.reasoning_effort)
        if p.api_key:
            self.api_key.set(p.api_key)
        if p.api_base_url:
            self.api_base_url.set(p.api_base_url)
        if p.api_version:
            self.api_version.set(p.api_version)
        if p.api_mode:
            self.api_mode.set(p.api_mode)
        if t.target_language:
            self.target_language.set(t.target_language)
        if t.custom_prompt:
            self.custom_prompt_box.delete("1.0", "end")
            self.custom_prompt_box.insert("1.0", t.custom_prompt)
        self.bilingual.set(t.bilingual_output)
        self.context_window.set(t.context_window_blocks)
        self.max_chars.set(c.max_chars)
        self.max_tokens.set(c.max_tokens)
        self.test_limit.set(c.test_limit)
        self.start_page.set(inp.start_page)
        self.end_page.set(inp.end_page)
        if g.path:
            self.glossary_path.set(g.path)
        if o.output_dir:
            self.output_dir.set(o.output_dir)
        # Update model dropdown for the loaded provider
        self._on_provider_changed()
        self._append_log(f"Loaded config: {config_path}")

    def _choose_env(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".env", filetypes=[("Env", ".env"), ("All files", "*.*")])
        if path:
            self.env_file.set(path)

    def _choose_output_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def _choose_glossary(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Glossary", "*.csv *.xlsx *.xls"), ("All files", "*.*")]
        )
        if path:
            self.glossary_path.set(path)
            self._refresh_resume_status()

    def _save_example_config(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".toml", filetypes=[("TOML", "*.toml")])
        if not path:
            return
        form = self._collect_form()
        custom_prompt = form.get("custom_prompt", "")
        # Escape TOML multiline: use triple-quoted string
        if "\n" in custom_prompt:
            prompt_value = f'"""\n{custom_prompt}\n"""'
        else:
            prompt_value = f'"{custom_prompt}"'
        content = f"""[provider]
# kind: codex, claude, gemini, openai, azure, compatible, or mock
kind = "{form.get("provider", "codex")}"
model = "{form.get("model", "gpt-5.2-codex")}"
reasoning_effort = "{form.get("reasoning_effort", "medium")}"
api_key = "{form.get("api_key", "")}"
api_base_url = "{form.get("api_base_url", "")}"
api_version = "{form.get("api_version", "")}"
api_mode = "{form.get("api_mode", "auto")}"
timeout_seconds = 120
max_retries = 5
proxy = ""

[translation]
target_language = "{form.get("target_language", "Simplified Chinese")}"
bilingual_output = {str(form.get("bilingual", False)).lower()}
custom_prompt = {prompt_value}
temperature = 0.2
max_output_tokens = 0
preserve_line_breaks = true
context_window_blocks = {form.get("context_window", 6)}

[chunking]
max_chars = {form.get("max_chars", 5000)}
max_tokens = {form.get("max_tokens", 3500)}
test_limit = {form.get("test_limit", 3)}

[input]
start_page = {form.get("start_page", 1)}
end_page = {form.get("end_page", -1)}

[glossary]
path = "{form.get("glossary_path", "")}"
case_sensitive = false

[output]
output_dir = "{form.get("output_dir", "output")}"
emit_txt = true
emit_epub = true
skip_existing = {str(form.get("skip_existing", False)).lower()}
overwrite = {str(form.get("overwrite", False)).lower()}
write_manifest = true

[runtime]
dry_run = false
test_mode = false
cache_path = ".cache/translation.sqlite3"
job_dir = ".cache/jobs"
"""
        Path(path).write_text(content, encoding="utf-8")
        self._append_log(f"Saved config to {path}")

    def _open_output_dir(self) -> None:
        output_dir = Path(self.output_dir.get() or "output")
        output_dir.mkdir(parents=True, exist_ok=True)
        if shutil.which("xdg-open"):
            subprocess.run(["xdg-open", str(output_dir)], check=False)
        elif shutil.which("open"):
            subprocess.run(["open", str(output_dir)], check=False)
        else:
            self._append_log(f"Output directory: {output_dir}")

    def _run_codex_login(self) -> None:
        self._run_cli_login("codex", "codex", "codex login")

    def _run_claude_login(self) -> None:
        self._run_cli_login("claude", "Claude Code", "claude")

    def _run_gemini_login(self) -> None:
        self._run_cli_login("gemini", "Gemini", "gemini auth login")

    def _run_cli_login(self, cli_name: str, display_name: str, login_cmd: str) -> None:
        cmd = shutil.which(cli_name)
        if not cmd:
            messagebox.showerror(f"{display_name} not found", f"{display_name} CLI was not found in PATH.")
            return
        terminal = _detect_terminal()
        if terminal:
            subprocess.Popen([*terminal, login_cmd])
            self._append_log(f"Launched `{login_cmd}` in an external terminal.")
        else:
            messagebox.showinfo("Run in terminal", f"No terminal emulator detected. Run `{login_cmd}` in your shell.")

    def _refresh_cli_status(self) -> None:
        self.codex_status.set(self._get_cli_status("codex"))
        self.claude_status.set(self._get_cli_status("claude"))
        self.gemini_status.set(self._get_cli_status("gemini"))
        self._append_log(f"Codex: {self.codex_status.get()}")
        self._append_log(f"Claude: {self.claude_status.get()}")
        self._append_log(f"Gemini: {self.gemini_status.get()}")

    def _refresh_resume_status(self, log_message: bool = False) -> None:
        form = self._collect_form()
        input_file = Path(form["file_path"]) if form["file_path"] else None
        if input_file is None or not input_file.exists():
            self.resume_status.set("Select an input file to check whether resumable progress exists.")
            return
        try:
            config = build_config_from_form(form)
            status = inspect_resume_state(input_file, config)
        except Exception as exc:
            self.resume_status.set(f"Resume check failed: {exc}")
            return
        message = status.message
        if status.memory_path:
            message = f"{message} Memory: {status.memory_path}"
        self.resume_status.set(message)
        if log_message:
            self._append_log(message)

    def _list_models(self) -> None:
        provider = self.provider.get().strip().lower()
        # Refresh defaults
        if provider == "claude":
            self.claude_model_choices = load_claude_model_choices()
        elif provider == "gemini":
            self.gemini_model_choices = load_gemini_model_choices()
        else:
            self.codex_model_choices = load_codex_model_choices()
        models = self._get_model_choices(provider)
        self.model_combo.configure(values=models)
        if not models:
            self._append_log(f"No {provider} models found.")
            return
        custom = set(self.custom_models.get(provider, []))
        self._append_log(f"{provider} models:")
        for model in models[:30]:
            suffix = " (custom)" if model in custom else ""
            self._append_log(f"- {model}{suffix}")

    def _on_provider_changed(self) -> None:
        provider = self.provider.get().strip().lower()
        if provider == "codex":
            self.codex_model_choices = load_codex_model_choices()
        elif provider == "claude":
            self.claude_model_choices = load_claude_model_choices()
        elif provider == "gemini":
            self.gemini_model_choices = load_gemini_model_choices()
        choices = self._get_model_choices(provider)
        self.model_combo.configure(values=choices)
        if self.model.get() not in choices and choices:
            self.model.set(choices[0])
        self._refresh_resume_status()

    def _start_translation(self, resume_only: bool = False) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Translation running", "A translation task is already running.")
            return
        if not self.file_path.get().strip():
            messagebox.showerror("Missing input", "Please choose an input file.")
            return

        form = self._collect_form()
        force = self.force_resume.get()
        if resume_only:
            config = build_config_from_form(form)
            status = inspect_resume_state(Path(self.file_path.get()), config)
            message = status.message
            if not status.available:
                messagebox.showinfo("No resumable job", message)
                self.resume_status.set(message)
                return
            if not status.compatible and not force:
                messagebox.showinfo("No resumable job", message)
                self.resume_status.set(message)
                return
            if not status.compatible and force:
                message = (
                    f"Force resume: reusing {status.completed_blocks}/{status.total_blocks or '?'} "
                    f"previously translated blocks (params changed)."
                )
            self.resume_status.set(message)
            self._append_log(message)

        self.status_text.set("Running")
        self.progress_value.set(0.0)
        self.progress_detail.set("Preparing translation job...")
        self._append_log(f"Starting translation for {self.file_path.get()}")
        self.worker = threading.Thread(target=self._run_translation, args=(form, force), daemon=True)
        self.worker.start()

    def _collect_form(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path.get().strip(),
            "config_path": self.config_path.get().strip(),
            "env_file": self.env_file.get().strip(),
            "provider": self.provider.get().strip(),
            "model": self.model.get().strip(),
            "reasoning_effort": self.reasoning_effort.get().strip(),
            "api_key": self.api_key.get().strip(),
            "api_base_url": self.api_base_url.get().strip(),
            "api_version": self.api_version.get().strip(),
            "api_mode": self.api_mode.get().strip(),
            "target_language": self.target_language.get().strip(),
            "custom_prompt": self.custom_prompt_box.get("1.0", "end").strip(),
            "context_window": self.context_window.get(),
            "glossary_path": self.glossary_path.get().strip(),
            "bilingual": self.bilingual.get(),
            "dry_run": self.dry_run.get(),
            "test_mode": self.test_mode.get(),
            "test_limit": self.test_limit.get(),
            "max_chars": self.max_chars.get(),
            "max_tokens": self.max_tokens.get(),
            "start_page": self.start_page.get(),
            "end_page": self.end_page.get(),
            "output_dir": self.output_dir.get().strip(),
            "txt_only": self.txt_only.get(),
            "epub_only": self.epub_only.get(),
            "skip_existing": self.skip_existing.get(),
            "overwrite": self.overwrite.get(),
        }

    def _run_translation(self, form: dict[str, Any], force_resume: bool = False) -> None:
        try:
            config = build_config_from_form(form)
            document, artifacts, stats = translate_file(
                Path(self.file_path.get()),
                config,
                progress_callback=lambda event: self.queue.put(("progress", asdict(event))),
                force_resume=force_resume,
            )
            payload = {
                "document": document.title,
                "artifacts": asdict(artifacts),
                "stats": asdict(stats),
            }
            self.queue.put(("success", payload))
        except Exception as exc:  # pragma: no cover
            self.queue.put(("error", {"error": str(exc), "traceback": traceback.format_exc()}))

    def _process_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "progress":
                    self._handle_progress(payload)
                elif kind == "success":
                    self.status_text.set("Done")
                    self.progress_value.set(100.0)
                    self.progress_detail.set("Translation completed.")
                    self._append_log(f"Finished: {payload['document']}")
                    for key, value in payload["artifacts"].items():
                        if value:
                            self._append_log(f"{key}: {value}")
                    self._append_log(
                        "stats: "
                        + ", ".join(f"{key}={value}" for key, value in payload["stats"].items())
                    )
                    self._refresh_resume_status()
                    self._refresh_cli_status()
                elif kind == "error":
                    self.status_text.set("Failed")
                    self.progress_detail.set("Translation failed.")
                    self._append_log(f"ERROR: {payload['error']}")
                    self._append_log(payload["traceback"])
                    messagebox.showerror("Translation failed", payload["error"])
        except Empty:
            pass
        self.root.after(150, self._process_queue)

    def _handle_progress(self, payload: dict[str, Any]) -> None:
        total_blocks = int(payload.get("total_blocks", 0) or 0)
        completed_blocks = int(payload.get("completed_blocks", 0) or 0)
        current_block_index = int(payload.get("current_block_index", 0) or 0)
        current_chunk_index = int(payload.get("current_chunk_index", 0) or 0)
        total_chunks = int(payload.get("total_chunks", 0) or 0)
        stage = str(payload.get("stage", ""))
        chapter_title = str(payload.get("chapter_title", "")).strip()
        cache_hits = int(payload.get("cache_hits", 0) or 0)
        api_calls = int(payload.get("api_calls", 0) or 0)
        message = str(payload.get("message", "")).strip()

        if total_blocks > 0:
            percent = (completed_blocks / total_blocks) * 100
            if stage in {"block_started", "chunk_started", "chunk_finished"} and current_block_index:
                block_base = (current_block_index - 1) / total_blocks
                chunk_fraction = 0.0
                if total_chunks > 0:
                    finished_chunks = current_chunk_index
                    if stage == "chunk_started":
                        finished_chunks = max(0, current_chunk_index - 1)
                    chunk_fraction = finished_chunks / total_chunks
                percent = max(percent, (block_base + (chunk_fraction / total_blocks)) * 100)
            self.progress_value.set(min(100.0, percent))

        detail_parts = []
        if total_blocks:
            detail_parts.append(f"Blocks {completed_blocks}/{total_blocks}")
        if current_block_index:
            detail_parts.append(f"Current block {current_block_index}")
        if total_chunks:
            detail_parts.append(f"Chunk {current_chunk_index}/{total_chunks}")
        if chapter_title:
            detail_parts.append(chapter_title)
        detail_parts.append(f"API {api_calls}")
        detail_parts.append(f"Cache {cache_hits}")
        if message:
            detail_parts.append(message)
        self.progress_detail.set(" | ".join(detail_parts))

        if stage in {"start", "block_started", "block_finished", "done"} and message:
            self._append_log(message)

    def _append_log(self, message: str) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", message + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    @staticmethod
    def _get_cli_status(cli_name: str) -> str:
        cli_path = shutil.which(cli_name)
        if not cli_path:
            return "not found"
        version_flag = "-v" if cli_name == "gemini" else "--version"
        try:
            completed = subprocess.run(
                [cli_path, version_flag],
                text=True, capture_output=True, check=False, timeout=5,
            )
        except subprocess.TimeoutExpired:
            return "installed (timeout)"
        if completed.returncode == 0:
            version = (completed.stdout or "").strip()
            return f"ready ({version})" if version else "ready"
        return "installed (check auth)"
        return "unknown"


def _detect_terminal() -> list[str] | None:
    candidates = [
        ["x-terminal-emulator", "-e"],
        ["gnome-terminal", "--"],
        ["konsole", "-e"],
        ["xterm", "-e"],
    ]
    for candidate in candidates:
        if shutil.which(candidate[0]):
            return candidate
    return None


if __name__ == "__main__":
    main()
