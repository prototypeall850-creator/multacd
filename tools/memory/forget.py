"""forget — hapus dari long-term memory. AUTO-APPROVED."""

from __future__ import annotations

from typing import Any

from memory import store
from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "forget",
        "description": "Hapus satu key dari long-term memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
            },
            "required": ["key"],
        },
    },
}


def forget(key: str) -> dict[str, Any]:
    try:
        deleted = store.forget(key)
    except OSError as e:
        return fail(f"Gagal hapus memory: {e}")
    if not deleted:
        return fail(f"Tidak ada memory dengan key: {key}")
    return ok(f"Dihapus: {key}")
