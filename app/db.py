"""SQLite storage for cases and the audit log (who approved what, and when)."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                doctor_token TEXT UNIQUE,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT
            );
            """
        )


def save_case(case: dict) -> None:
    case["updated_at"] = now_iso()
    with _lock, _connect() as conn:
        conn.execute(
            """INSERT INTO cases (id, created_at, updated_at, status, doctor_token, data)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,
                 status=excluded.status, doctor_token=excluded.doctor_token, data=excluded.data""",
            (case["id"], case["created_at"], case["updated_at"], case["status"],
             case.get("doctor_token"), json.dumps(case)),
        )


def get_case(case_id: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT data FROM cases WHERE id = ?", (case_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def get_case_by_token(token: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT data FROM cases WHERE doctor_token = ?", (token,)).fetchone()
    return json.loads(row["data"]) if row else None


def list_cases(limit: int = 50) -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT data FROM cases ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [json.loads(r["data"]) for r in rows]


def count_cases() -> int:
    with _lock, _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]


def add_audit(case_id: str, actor: str, action: str, detail: str = "") -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO audit (case_id, ts, actor, action, detail) VALUES (?, ?, ?, ?, ?)",
            (case_id, now_iso(), actor, action, detail),
        )


def get_audit(case_id: str) -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT ts, actor, action, detail FROM audit WHERE case_id = ? ORDER BY id",
            (case_id,),
        ).fetchall()
    return [dict(r) for r in rows]
