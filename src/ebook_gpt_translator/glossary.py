from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass(slots=True)
class Glossary:
    entries: list[tuple[str, str]] = field(default_factory=list)
    case_sensitive: bool = False

    @classmethod
    def from_path(cls, path: str, case_sensitive: bool = False) -> "Glossary":
        if not path:
            return cls(case_sensitive=case_sensitive)
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Glossary file not found: {file_path}")
        if file_path.suffix.lower() in {".xlsx", ".xls"}:
            try:
                dataframe = pd.read_excel(file_path)
            except ImportError as exc:
                raise RuntimeError(
                    "XLSX glossary support requires openpyxl. Install it with: "
                    "python3 -m pip install 'ebook-gpt-translator[xlsx]' or python3 -m pip install openpyxl"
                ) from exc
            rows = []
            for row in dataframe.itertuples(index=False):
                values = [str(value).strip() for value in row[:2]]
                if len(values) >= 2 and values[0]:
                    rows.append((values[0], values[1]))
        else:
            with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                rows = [
                    (row[0].strip(), row[1].strip())
                    for row in reader
                    if len(row) >= 2 and row[0].strip()
                ]
        return cls(entries=rows, case_sensitive=case_sensitive)

    def apply(self, text: str) -> str:
        updated = text
        flags = 0 if self.case_sensitive else re.IGNORECASE
        for source, target in self.entries:
            pattern = re.compile(re.escape(source), flags)
            updated = pattern.sub(target, updated)
        return updated

    def as_prompt_suffix(self) -> str:
        if not self.entries:
            return ""
        lines = ["Use the glossary below when the source term appears:"]
        lines.extend(f"- {source} => {target}" for source, target in self.entries)
        return "\n".join(lines)
