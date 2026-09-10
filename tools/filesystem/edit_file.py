"""edit_file — edit bagian spesifik file (cari & ganti). ASK-REQUIRED."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": "Ganti old_string dengan new_string di dalam file. old_string harus unik.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string", "description": "Teks yang dicari (harus muncul tepat 1x)."},
                "new_string": {"type": "string", "description": "Teks pengganti."},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
}


def edit_file(path: str, old_string: str, new_string: str) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.is_file():
        return fail(f"File tidak ditemukan: {path}")
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return fail(f"Gagal baca {path}: {e}")
    count = text.count(old_string)
    if count == 0:
        return fail(f"old_string tidak ditemukan di {path}")
    if count > 1:
        return fail(f"old_string muncul {count}x di {path} — harus unik, persempit konteksnya")
    p.write_text(text.replace(old_string, new_string, 1), encoding="utf-8")
    return ok(f"Diedit: {path}")
