"""recall — baca dari long-term memory. AUTO-APPROVED."""

from __future__ import annotations

from typing import Any

from memory import store
from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "recall",
        "description": "Baca long-term memory. Tanpa key = baca semua.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Kosongkan untuk baca semua."},
            },
            "required": [],
        },
    },
}


def recall(key: str = "") -> dict[str, Any]:
    try:
        if key:
            value = store.recall(key)
            if value is None:
                return fail(f"Tidak ada memory dengan key: {key}")
            return ok(value)
        return ok(store.recall_all())
    except OSError as e:
        return fail(f"Gagal baca memory: {e}")
