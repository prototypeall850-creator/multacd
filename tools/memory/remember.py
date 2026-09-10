"""remember — simpan ke long-term memory. AUTO-APPROVED."""

from __future__ import annotations

from typing import Any

from memory import store
from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "remember",
        "description": "Simpan info key-value ke long-term memory (antar sesi).",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
}


def remember(key: str, value: str) -> dict[str, Any]:
    try:
        store.remember(key, value)
    except ValueError as e:
        return fail(str(e))
    except OSError as e:
        return fail(f"Gagal simpan memory: {e}")
    return ok(f"Tersimpan: {key}")
