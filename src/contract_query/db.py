from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial_no INTEGER,
    contract_no TEXT,
    contract_name TEXT,
    project_no TEXT,
    project_name TEXT,
    purchaser TEXT,
    supplier TEXT,
    item_name TEXT,
    spec_or_service TEXT,
    item_quantity TEXT,
    unit_price_wan REAL,
    amount_wan REAL,
    purchase_method TEXT,
    signed_date TEXT,
    source_url TEXT,
    excel_contract_file TEXT,
    notes TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DROP INDEX IF EXISTS idx_contracts_contract_no_unique;
CREATE INDEX IF NOT EXISTS idx_contracts_contract_no ON contracts(contract_no);

CREATE INDEX IF NOT EXISTS idx_contracts_serial_no ON contracts(serial_no);
CREATE INDEX IF NOT EXISTS idx_contracts_supplier ON contracts(supplier);
CREATE INDEX IF NOT EXISTS idx_contracts_contract_name ON contracts(contract_name);
CREATE INDEX IF NOT EXISTS idx_contracts_project_name ON contracts(project_name);
CREATE INDEX IF NOT EXISTS idx_contracts_item_name ON contracts(item_name);
CREATE INDEX IF NOT EXISTS idx_contracts_signed_date ON contracts(signed_date);
CREATE INDEX IF NOT EXISTS idx_contracts_purchase_method ON contracts(purchase_method);

CREATE TABLE IF NOT EXISTS contract_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    file_ext TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    page_count INTEGER,
    text_status TEXT NOT NULL DEFAULT 'not_checked',
    match_method TEXT NOT NULL,
    checksum TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contract_files_contract_id ON contract_files(contract_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_contract_files_relative_path ON contract_files(relative_path);

CREATE TABLE IF NOT EXISTS import_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_excel TEXT NOT NULL,
    total_rows INTEGER NOT NULL,
    imported_rows INTEGER NOT NULL,
    matched_files INTEGER NOT NULL,
    unmatched_rows INTEGER NOT NULL,
    unmatched_files INTEGER NOT NULL,
    code_matched_files INTEGER NOT NULL DEFAULT 0,
    serial_prefix_matched_files INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL,
    message TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    contract_id INTEGER,
    file_id INTEGER,
    message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(db_path: Path) -> None:
    with connect(db_path) as conn:
        existing = conn.execute("PRAGMA table_info(contracts)").fetchall()
        columns = {row["name"] for row in existing}
        if existing and "contract_no" not in columns:
            conn.execute("DROP TABLE IF EXISTS contracts")
            conn.execute("DROP TABLE IF EXISTS contract_files")
            conn.execute("DROP TABLE IF EXISTS import_runs")
            conn.execute("DROP TABLE IF EXISTS audit_events")
        conn.executescript(SCHEMA)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, object] | None:
    return dict(row) if row else None
