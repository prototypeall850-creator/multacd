"""list_dir — lihat isi folder. AUTO-APPROVED."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "list_dir",
        "description": "List isi folder beserta info tipe & ukuran.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Folder yang dilihat.", "default": "."},
            },
            "required": [],
        },
    },
}


def list_dir(path: str = ".") -> dict[str, Any]:
    base = Path(path).expanduser()
    if not base.exists():
        return fail(f"Folder tidak ditemukan: {path}")
    if not base.is_dir():
        return fail(f"Bukan folder: {path}")
    try:
        entries = sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except OSError as e:
        return fail(f"Gagal baca folder {path}: {e}")
    lines: list[str] = []
    for p in entries:
        if p.is_dir():
            lines.append(f"dir  {p.name}/")
        else:
            try:
                size = p.stat().st_size
            except OSError:
                size = -1
            lines.append(f"file {p.name} ({size} bytes)")
    return ok("\n".join(lines) if lines else "(folder kosong)")
