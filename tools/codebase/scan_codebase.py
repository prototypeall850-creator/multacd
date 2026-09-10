"""scan_codebase — scan ulang struktur project. AUTO-APPROVED (read-only)."""

from __future__ import annotations

from typing import Any

from core.codebase import scan_project
from tools.common import ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "scan_codebase",
        "description": "Scan struktur project (folder, file kunci, git info). "
                       "Dipakai kalau user minta baca ulang project.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Root project.", "default": "."},
            },
            "required": [],
        },
    },
}


def scan_codebase(path: str = ".") -> dict[str, Any]:
    return ok(scan_project(path))
