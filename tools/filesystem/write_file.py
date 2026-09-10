"""write_file — tulis/buat file baru (overwrite kalau sudah ada). ASK-REQUIRED."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Tulis konten ke file (buat baru atau overwrite). Folder parent dibuat otomatis.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path file tujuan."},
                "content": {"type": "string", "description": "Isi file."},
            },
            "required": ["path", "content"],
        },
    },
}


def write_file(path: str, content: str) -> dict[str, Any]:
    p = Path(path).expanduser()
    try:
        if p.parent != Path("."):
            p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content, encoding="utf-8")
    except OSError as e:
        return fail(f"Gagal tulis {path}: {e}")
    action = "dioverwrite" if existed else "dibuat"
    return ok(f"File {action}: {path} ({len(content)} karakter)")
