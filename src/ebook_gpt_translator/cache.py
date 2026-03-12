from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ebook_gpt_translator.models import UsageStats


class TranslationCache:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS translations (
                cache_key TEXT PRIMARY KEY,
                translated_text TEXT NOT NULL,
                usage_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    @staticmethod
    def build_key(payload: dict[str, str]) -> str:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get(self, payload: dict[str, str]) -> tuple[str, dict[str, int]] | None:
        cache_key = self.build_key(payload)
        row = self.connection.execute(
            "SELECT translated_text, usage_json FROM translations WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        return row["translated_text"], json.loads(row["usage_json"])

    def put(self, payload: dict[str, str], translated_text: str, usage: dict[str, int]) -> None:
        cache_key = self.build_key(payload)
        self.connection.execute(
            """
            INSERT OR REPLACE INTO translations (cache_key, translated_text, usage_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                cache_key,
                translated_text,
                json.dumps(usage, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


def write_manifest(path: Path, payload: dict, stats: UsageStats) -> None:
    data = dict(payload)
    data["stats"] = asdict(stats)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
