"""ask — minta input/konfirmasi ke user. AUTO-APPROVED.

Di TUI, agent_loop mencegat tool ini dan menampilkannya sebagai
dialog interaktif (tidak lewat fungsi ini). Fungsi di bawah hanya
fallback CLI (baca dari stdin).
"""

from __future__ import annotations

from typing import Any

from tools.common import ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "ask",
        "description": "Tanyakan sesuatu ke user dan tunggu jawabannya.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Pertanyaan ke user."},
            },
            "required": ["question"],
        },
    },
}


def ask(question: str) -> dict[str, Any]:
    try:
        answer = input(f"❓ {question}\nJawaban: ")
    except (EOFError, KeyboardInterrupt):
        return ok("(user membatalkan pertanyaan)")
    return ok(answer)
