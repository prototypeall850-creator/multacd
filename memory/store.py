"""Long-term memory — SQLite di ~/.multacd/memory.db.

Dipakai langsung oleh tools/memory/{remember,recall,forget}.py.
Dibangun duluan di Step 5d karena tool memory butuh store ini;
Step 6 nanti menambah short-term context (memory/context.py).
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path


def db_path() -> Path:
    base = Path(os.environ.get("MULTACD_HOME", str(Path.home())))
    d = base / ".multacd"
    d.mkdir(parents=True, exist_ok=True)
    return d / "memory.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL
)
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.execute(_SCHEMA)
    return conn


def remember(key: str, value: str) -> None:
    if not key.strip():
        raise ValueError("key tidak boleh kosong")
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO memories(key, value, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key.strip(), value, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def recall(key: str) -> str | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM memories WHERE key=?", (key.strip(),)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def recall_all() -> dict[str, str]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT key, value FROM memories ORDER BY key").fetchall()
    finally:
        conn.close()
    return {k: v for k, v in rows}


def forget(key: str) -> bool:
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM memories WHERE key=?", (key.strip(),))
        conn.commit()
    finally:
        conn.close()
    return cur.rowcount > 0
