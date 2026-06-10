from __future__ import annotations

from pathlib import Path
from typing import Any

from .db import connect, initialize_database, row_to_dict

SEARCH_COLUMNS = [
    "c.contract_no",
    "c.contract_name",
    "c.project_no",
    "c.project_name",
    "c.purchaser",
    "c.supplier",
    "c.item_name",
    "c.spec_or_service",
    "c.purchase_method",
    "c.signed_date",
    "CAST(c.amount_wan AS TEXT)",
    "printf('%.2f', c.amount_wan)",
    "c.excel_contract_file",
    "c.notes",
    "f.original_filename",
]


def search_contracts(
    db_path: Path,
    query: str = "",
    limit: int = 20,
    year: str = "",
    supplier: str = "",
    purchase_method: str = "",
    min_amount: float | None = None,
    max_amount: float | None = None,
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    clauses = ["c.status = 'active'"]
    params: list[Any] = []
    if query:
        clauses.append("(" + " OR ".join(f"{column} LIKE ?" for column in SEARCH_COLUMNS) + ")")
        params.extend([f"%{query}%"] * len(SEARCH_COLUMNS))
    if year:
        clauses.append("c.signed_date LIKE ?")
        params.append(f"{year}%")
    if supplier:
        clauses.append("c.supplier LIKE ?")
        params.append(f"%{supplier}%")
    if purchase_method:
        clauses.append("c.purchase_method = ?")
        params.append(purchase_method)
    if min_amount is not None:
        clauses.append("c.amount_wan >= ?")
        params.append(min_amount)
    if max_amount is not None:
        clauses.append("c.amount_wan <= ?")
        params.append(max_amount)
    params.append(limit)
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                c.id, c.serial_no, c.contract_no, c.contract_name, c.project_no, c.project_name,
                c.purchaser, c.supplier, c.item_name, c.spec_or_service, c.item_quantity,
                c.unit_price_wan, c.amount_wan, c.purchase_method, c.signed_date,
                c.source_url, c.excel_contract_file, c.notes, c.status, c.created_at, c.updated_at,
                f.id AS file_id, f.original_filename, f.relative_path, f.size_bytes AS file_size_bytes,
                f.page_count, f.text_status, f.match_method
            FROM contracts c
            LEFT JOIN contract_files f ON f.contract_id = c.id
            WHERE {' AND '.join(clauses)}
            ORDER BY c.serial_no IS NULL, c.serial_no, c.id
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def get_contract(db_path: Path, contract_id: int) -> dict[str, Any] | None:
    if not db_path.exists():
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM contracts WHERE id = ? AND status = 'active'
            """,
            (contract_id,),
        ).fetchone()
        contract = row_to_dict(row)
        if contract is None:
            return None
        files = conn.execute(
            """
            SELECT id, original_filename, relative_path, file_ext, size_bytes, page_count,
                   text_status, match_method, checksum, created_at
            FROM contract_files
            WHERE contract_id = ?
            ORDER BY id
            """,
            (contract_id,),
        ).fetchall()
    contract["files"] = [dict(file_row) for file_row in files]
    return contract


def get_file_record(db_path: Path, file_id: int) -> dict[str, Any] | None:
    if not db_path.exists():
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT f.*, c.contract_name, c.contract_no
            FROM contract_files f
            JOIN contracts c ON c.id = f.contract_id
            WHERE f.id = ? AND c.status = 'active'
            """,
            (file_id,),
        ).fetchone()
    return row_to_dict(row)


def stats(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {"contracts": 0, "files": 0, "total_amount_wan": 0, "last_import": None}
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM contracts WHERE status = 'active') AS contracts,
                (SELECT COUNT(*) FROM contract_files) AS files,
                (SELECT COALESCE(SUM(amount_wan), 0) FROM contracts WHERE status = 'active') AS total_amount_wan,
                (SELECT finished_at FROM import_runs ORDER BY id DESC LIMIT 1) AS last_import
            """
        ).fetchone()
    return dict(row)


def list_purchase_methods(db_path: Path) -> list[str]:
    if not db_path.exists():
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT purchase_method FROM contracts WHERE purchase_method != '' ORDER BY purchase_method"
        ).fetchall()
    return [row[0] for row in rows]


def list_signed_years(db_path: Path) -> list[str]:
    if not db_path.exists():
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT substr(signed_date, 1, 4) AS year
            FROM contracts
            WHERE status = 'active' AND signed_date GLOB '[0-9][0-9][0-9][0-9]*'
            ORDER BY year DESC
            """
        ).fetchall()
    return [row[0] for row in rows]


def add_contract(db_path: Path, payload: dict[str, Any], file_record: dict[str, Any] | None = None) -> int:
    initialize_database(db_path)
    with connect(db_path) as conn:
        contract_no = payload.get("contract_no", "")
        if contract_no:
            existing = conn.execute(
                "SELECT id FROM contracts WHERE contract_no = ? AND status = 'active' LIMIT 1",
                (contract_no,),
            ).fetchone()
            if existing:
                raise ValueError("合同编号已存在")
        cursor = conn.execute(
            """
            INSERT INTO contracts (
                serial_no, contract_no, contract_name, project_no, project_name,
                purchaser, supplier, item_name, spec_or_service, item_quantity,
                unit_price_wan, amount_wan, purchase_method, signed_date, source_url,
                excel_contract_file, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("serial_no"),
                contract_no,
                payload.get("contract_name", ""),
                payload.get("project_no", ""),
                payload.get("project_name", ""),
                payload.get("purchaser", ""),
                payload.get("supplier", ""),
                payload.get("item_name", ""),
                payload.get("spec_or_service", ""),
                payload.get("item_quantity", ""),
                payload.get("unit_price_wan"),
                payload.get("amount_wan"),
                payload.get("purchase_method", ""),
                payload.get("signed_date", ""),
                payload.get("source_url", ""),
                payload.get("excel_contract_file", ""),
                payload.get("notes", ""),
            ),
        )
        contract_id = int(cursor.lastrowid)
        if file_record:
            conn.execute(
                """
                INSERT INTO contract_files (
                    contract_id, original_filename, relative_path, file_ext, size_bytes,
                    page_count, text_status, match_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contract_id,
                    file_record["original_filename"],
                    file_record["relative_path"],
                    file_record["file_ext"],
                    file_record["size_bytes"],
                    file_record.get("page_count"),
                    file_record.get("text_status", "not_checked"),
                    "uploaded",
                ),
            )
        conn.execute(
            "INSERT INTO audit_events (event_type, contract_id, message) VALUES (?, ?, ?)",
            ("contract_created", contract_id, payload.get("contract_name", "")),
        )
    return contract_id
