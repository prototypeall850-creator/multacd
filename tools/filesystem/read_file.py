"""read_file — baca isi satu file. AUTO-APPROVED."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.common import fail, ok

MAX_CHARS = 100_000  # jaga-jaga biar context LLM tidak jebol

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Baca isi satu file teks, return sebagai string.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path file (relatif cwd atau absolut)."},
            },
            "required": ["path"],
        },
    },
}


def read_file(path: str) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.exists():
        return fail(f"File tidak ditemukan: {path}")
    if not p.is_file():
        return fail(f"Bukan file: {path}")
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return fail(f"File bukan teks (binary?): {path}")
    except OSError as e:
        return fail(f"Gagal baca {path}: {e}")
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + f"\n[...dipotong: file > {MAX_CHARS} karakter...]"
    return ok(text)
