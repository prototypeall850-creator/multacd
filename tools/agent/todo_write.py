"""todo_write — tulis & update todo list agent. AUTO-APPROVED."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "todo_write",
        "description": "Tulis todo.md di working directory dari daftar todo.",
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "status": {"type": "string",
                                       "enum": ["pending", "in_progress", "done"]},
                        },
                        "required": ["content", "status"],
                    },
                },
                "workdir": {"type": "string", "default": "."},
            },
            "required": ["todos"],
        },
    },
}

_CHECK = {"pending": " ", "in_progress": "~", "done": "x"}


def todo_write(todos: list[dict[str, str]], workdir: str = ".") -> dict[str, Any]:
    if not todos:
        return fail("Daftar todos kosong.")
    lines = ["# Todo\n"]
    for t in todos:
        status = t.get("status", "pending")
        if status not in _CHECK:
            return fail(f"status tidak valid: {status} (pakai pending|in_progress|done)")
        lines.append(f"- [{_CHECK[status]}] {t.get('content', '')}")
    target = Path(workdir).expanduser() / "todo.md"
    try:
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as e:
        return fail(f"Gagal tulis todo.md: {e}")
    return ok(f"todo.md ditulis ({len(todos)} item): {target}")
