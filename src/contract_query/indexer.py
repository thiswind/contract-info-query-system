from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import Settings, ensure_runtime_dirs

INDEXED_SUFFIXES = {".pdf", ".xls", ".xlsx", ".csv", ".tsv", ".doc", ".docx", ".txt"}


@dataclass(frozen=True)
class InventorySummary:
    raw_dir: str
    total_files: int
    indexed_candidates: int
    by_suffix: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def iter_contract_files(raw_dir: Path):
    if not raw_dir.exists():
        return
    for path in sorted(raw_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in INDEXED_SUFFIXES:
            yield path


def inventory(settings: Settings) -> InventorySummary:
    suffix_counts: dict[str, int] = {}
    total_files = 0
    indexed_candidates = 0
    if settings.raw_dir.exists():
        for path in settings.raw_dir.rglob("*"):
            if not path.is_file():
                continue
            total_files += 1
            suffix = path.suffix.lower() or "[no suffix]"
            suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
            if path.suffix.lower() in INDEXED_SUFFIXES:
                indexed_candidates += 1
    return InventorySummary(
        raw_dir=str(settings.raw_dir),
        total_files=total_files,
        indexed_candidates=indexed_candidates,
        by_suffix=dict(sorted(suffix_counts.items())),
    )


def initialize_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                relative_path TEXT NOT NULL UNIQUE,
                suffix TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                modified_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_contracts_title ON contracts(title)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_contracts_suffix ON contracts(suffix)")


def build_index(settings: Settings) -> dict[str, object]:
    ensure_runtime_dirs(settings)
    initialize_database(settings.db_path)
    indexed = 0
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute("DELETE FROM contracts")
        for path in iter_contract_files(settings.raw_dir) or []:
            stat = path.stat()
            relative_path = path.relative_to(settings.raw_dir).as_posix()
            conn.execute(
                """
                INSERT INTO contracts (title, relative_path, suffix, size_bytes, modified_at)
                VALUES (?, ?, ?, ?, datetime(?, 'unixepoch'))
                """,
                (path.stem, relative_path, path.suffix.lower(), stat.st_size, int(stat.st_mtime)),
            )
            indexed += 1
    return {"db_path": str(settings.db_path), "indexed": indexed}
