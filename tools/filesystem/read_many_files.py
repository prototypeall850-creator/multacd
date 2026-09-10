"""read_many_files — baca beberapa file sekaligus. AUTO-APPROVED."""

from __future__ import annotations

from typing import Any

from tools.common import ok
from tools.filesystem.read_file import read_file

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_many_files",
        "description": "Baca beberapa file sekaligus. Return dict {path: isi atau pesan error}.",
        "parameters": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Daftar path file.",
                },
            },
            "required": ["paths"],
        },
    },
}


def read_many_files(paths: list[str]) -> dict[str, Any]:
    out: dict[str, str] = {}
    for path in paths:
        res = read_file(path)
        out[path] = res["result"] if res["success"] else f"ERROR: {res['error']}"
    return ok(out)
