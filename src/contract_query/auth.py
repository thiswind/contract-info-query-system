from __future__ import annotations

import base64
import hashlib
import hmac
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_bytes, token_urlsafe
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import Settings, load_session_secret
from .db import connect, initialize_database, row_to_dict

SESSION_COOKIE = "contract_query_session"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
PASSWORD_HASH_ITERATIONS = 260_000


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_password(password: str) -> str:
    salt = token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_HASH_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def generate_password() -> str:
    return token_urlsafe(18)


def audit(db_path: Path, event_type: str, message: str, contract_id: int | None = None, file_id: int | None = None) -> None:
    initialize_database(db_path)
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO audit_events (event_type, contract_id, file_id, message) VALUES (?, ?, ?, ?)",
            (event_type, contract_id, file_id, message),
        )


def create_user(
    db_path: Path,
    username: str,
    password: str,
    role: str,
    display_name: str = "",
    must_change_password: bool = False,
) -> dict[str, Any]:
    initialize_database(db_path)
    username = username.strip()
    if not username:
        raise ValueError("用户名不能为空")
    if role not in {"admin", "viewer"}:
        raise ValueError("角色无效")
    try:
        with connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role, display_name, must_change_password)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, hash_password(password), role, display_name.strip(), int(must_change_password)),
            )
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            conn.execute(
                "INSERT INTO audit_events (event_type, message) VALUES (?, ?)",
                ("user_created", f"{username}:{role}"),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("用户名已存在") from exc
    return dict(row)


def get_user(db_path: Path, username: str) -> dict[str, Any] | None:
    if not db_path.exists():
        return None
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
    return row_to_dict(row)


def get_user_by_id(db_path: Path, user_id: int) -> dict[str, Any] | None:
    if not db_path.exists():
        return None
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return row_to_dict(row)


def list_users(db_path: Path) -> list[dict[str, Any]]:
    initialize_database(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, username, role, display_name, is_active, must_change_password, last_login_at, created_at, updated_at
            FROM users
            ORDER BY role, username
            """
        ).fetchall()
    return [dict(row) for row in rows]


def authenticate_user(db_path: Path, username: str, password: str) -> dict[str, Any] | None:
    user = get_user(db_path, username)
    if user is None or not user["is_active"]:
        audit(db_path, "login_failed", username.strip())
        return None
    if not verify_password(password, str(user["password_hash"])):
        audit(db_path, "login_failed", username.strip())
        return None
    with connect(db_path) as conn:
        conn.execute("UPDATE users SET last_login_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (now_iso(), user["id"]))
        conn.execute("INSERT INTO audit_events (event_type, message) VALUES (?, ?)", ("login_success", user["username"]))
    user["last_login_at"] = now_iso()
    return user


def reset_user_password(db_path: Path, username: str, require_admin: bool = False) -> str:
    user = get_user(db_path, username)
    if user is None:
        raise ValueError("用户不存在")
    if require_admin and user["role"] != "admin":
        raise ValueError("只能重置管理员账号")
    password = generate_password()
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?, must_change_password = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (hash_password(password), user["id"]),
        )
        conn.execute(
            "INSERT INTO audit_events (event_type, message) VALUES (?, ?)",
            ("password_reset", str(user["username"])),
        )
    return password


def set_user_active(db_path: Path, username: str, is_active: bool) -> None:
    user = get_user(db_path, username)
    if user is None:
        raise ValueError("用户不存在")
    if user["role"] == "admin" and not is_active:
        raise ValueError("不能禁用管理员账号")
    with connect(db_path) as conn:
        conn.execute("UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (int(is_active), user["id"]))
        conn.execute(
            "INSERT INTO audit_events (event_type, message) VALUES (?, ?)",
            ("user_enabled" if is_active else "user_disabled", str(user["username"])),
        )


def ensure_admin_user(db_path: Path) -> str | None:
    initialize_database(db_path)
    with connect(db_path) as conn:
        existing = conn.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1").fetchone()
    if existing:
        return None
    password = generate_password()
    create_user(db_path, "admin", password, "admin", "系统管理员", must_change_password=True)
    audit(db_path, "admin_initialized", "admin")
    return password


def ensure_viewer_user(db_path: Path, username: str = "query") -> str | None:
    initialize_database(db_path)
    if get_user(db_path, username) is not None:
        return None
    password = generate_password()
    create_user(db_path, username, password, "viewer", "公共查询账号", must_change_password=False)
    return password


def session_serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(load_session_secret(settings), salt="contract-query-session")


def create_session_cookie(settings: Settings, user: dict[str, Any]) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=SESSION_MAX_AGE_SECONDS)
    return session_serializer(settings).dumps(
        {
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "expires_at": int(expires_at.timestamp()),
        }
    )


def load_session_user(settings: Settings, cookie_value: str | None) -> dict[str, Any] | None:
    if not cookie_value:
        return None
    try:
        payload = session_serializer(settings).loads(cookie_value, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    if int(payload.get("expires_at", 0)) < int(datetime.now(timezone.utc).timestamp()):
        return None
    user = get_user_by_id(settings.db_path, int(payload.get("user_id", 0)))
    if user is None or not user["is_active"]:
        return None
    if user["username"] != payload.get("username") or user["role"] != payload.get("role"):
        return None
    return user
