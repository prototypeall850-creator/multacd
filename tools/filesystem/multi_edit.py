"""multi_edit — kumpulan edit dalam satu call. ASK-REQUIRED."""

from __future__ import annotations

from typing import Any

from tools.common import fail, ok
from tools.filesystem.edit_file import edit_file

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "multi_edit",
        "description": "Lakukan beberapa edit_file sekaligus. Berhenti di edit pertama yang gagal.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_string": {"type": "string"},
                            "new_string": {"type": "string"},
                        },
                        "required": ["old_string", "new_string"],
                    },
                },
            },
            "required": ["path", "edits"],
        },
    },
}


def multi_edit(path: str, edits: list[dict[str, str]]) -> dict[str, Any]:
    if not edits:
        return fail("Daftar edits kosong.")
    done = 0
    for e in edits:
        res = edit_file(path, e["old_string"], e["new_string"])
        if not res["success"]:
            return fail(f"Edit ke-{done + 1} gagal ({done} sudah diterapkan): {res['error']}")
        done += 1
    return ok(f"{done} edit diterapkan ke {path}")
