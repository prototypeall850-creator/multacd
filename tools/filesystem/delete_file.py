"""delete_file — hapus file. ASK-REQUIRED. ⚠️ Tidak bisa di-undo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "delete_file",
        "description": "Hapus satu file. PERMANEN, tidak bisa di-undo.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
}


def delete_file(path: str) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.exists():
        return fail(f"File tidak ditemukan: {path}")
    if not p.is_file():
        return fail(f"Menolak: {path} bukan file (hanya file yang boleh dihapus)")
    try:
        p.unlink()
    except OSError as e:
        return fail(f"Gagal hapus {path}: {e}")
    return ok(f"Dihapus: {path}")
