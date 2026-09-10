"""task — spawn subtask ke agent. AUTO-APPROVED.

PLACEHOLDER Phase 1: implementasi penuh (sub-agent) di Phase 2.
Sekarang return pesan agar LLM mengerjakan langsung sendiri.
"""

from __future__ import annotations

from typing import Any

from tools.common import ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "task",
        "description": "Delegasikan subtask ke sub-agent (belum tersedia — kerjakan langsung).",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Deskripsi subtask."},
            },
            "required": ["description"],
        },
    },
}


def task(description: str) -> dict[str, Any]:
    return ok(
        "Sub-agent belum tersedia di Phase 1 (penuh di Phase 2). "
        f"Kerjakan sendiri subtask ini: {description}"
    )
