"""glob — cari file by pattern. AUTO-APPROVED."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "glob",
        "description": "Cari file berdasarkan pattern (mis. *.py, src/**/*.ts).",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, mis. **/*.py"},
                "path": {"type": "string", "description": "Folder awal pencarian.", "default": "."},
            },
            "required": ["pattern"],
        },
    },
}


def glob(pattern: str, path: str = ".") -> dict[str, Any]:
    base = Path(path).expanduser()
    if not base.exists():
        return fail(f"Folder tidak ditemukan: {path}")
    try:
        matches = sorted(str(p) for p in base.glob(pattern) if p.is_file())
    except Exception as e:
        return fail(f"Pattern tidak valid `{pattern}`: {e}")
    return ok(matches)
