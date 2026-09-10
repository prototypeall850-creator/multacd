"""move_file — pindah/rename file. ASK-REQUIRED."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "move_file",
        "description": "Pindah atau rename file (termasuk antar folder).",
        "parameters": {
            "type": "object",
            "properties": {
                "src": {"type": "string"},
                "dst": {"type": "string"},
            },
            "required": ["src", "dst"],
        },
    },
}


def move_file(src: str, dst: str) -> dict[str, Any]:
    s, d = Path(src).expanduser(), Path(dst).expanduser()
    if not s.exists():
        return fail(f"Sumber tidak ditemukan: {src}")
    if d.exists():
        return fail(f"Tujuan sudah ada (tidak dioverwrite): {dst}")
    try:
        d.parent.mkdir(parents=True, exist_ok=True)
        s.rename(d)
    except OSError as e:
        return fail(f"Gagal pindah {src} → {dst}: {e}")
    return ok(f"Dipindah: {src} → {dst}")
