from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    workspace: Path
    data_dir: Path
    raw_dir: Path
    processed_dir: Path
    db_path: Path
    host: str
    port: int
    root_path: str


def normalize_root_path(value: str) -> str:
    root_path = value.strip().rstrip("/")
    if not root_path:
        return ""
    if not root_path.startswith("/"):
        return f"/{root_path}"
    return root_path


def load_settings() -> Settings:
    load_dotenv()
    workspace = Path(os.getenv("CONTRACT_QUERY_WORKSPACE", Path.cwd())).expanduser().resolve()
    data_dir = Path(os.getenv("CONTRACT_QUERY_DATA_DIR", workspace / "data")).expanduser().resolve()
    raw_dir = Path(os.getenv("CONTRACT_QUERY_RAW_DIR", data_dir / "raw")).expanduser().resolve()
    processed_dir = Path(os.getenv("CONTRACT_QUERY_PROCESSED_DIR", data_dir / "processed")).expanduser().resolve()
    db_path = Path(os.getenv("CONTRACT_QUERY_DB", processed_dir / "contracts.sqlite3")).expanduser().resolve()
    host = os.getenv("CONTRACT_QUERY_HOST", "127.0.0.1")
    port = int(os.getenv("CONTRACT_QUERY_PORT", "8000"))
    root_path = normalize_root_path(os.getenv("CONTRACT_QUERY_ROOT_PATH", "/contract-query"))
    return Settings(
        workspace=workspace,
        data_dir=data_dir,
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        db_path=db_path,
        host=host,
        port=port,
        root_path=root_path,
    )


def ensure_runtime_dirs(settings: Settings) -> None:
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
