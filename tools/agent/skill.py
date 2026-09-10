"""skill — simpan & load skill (.md) di ~/.multacd/skills/. AUTO-APPROVED."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "skill",
        "description": "Kelola skill: save (simpan), load (baca), list (daftar).",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["save", "load", "list"]},
                "name": {"type": "string", "description": "Nama skill (tanpa .md). Wajib untuk save/load."},
                "content": {"type": "string", "description": "Isi markdown. Wajib untuk save."},
            },
            "required": ["action"],
        },
    },
}


def _skills_dir() -> Path:
    base = Path(os.environ.get("MULTACD_HOME", str(Path.home())))
    d = base / ".multacd" / "skills"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_name(name: str) -> str:
    cleaned = "".join(c if (c.isalnum() or c in "-_") else "-" for c in name.strip())
    return cleaned.strip("-") or "untitled"


def skill(action: str, name: str = "", content: str = "") -> dict[str, Any]:
    try:
        skills = _skills_dir()
    except OSError as e:
        return fail(f"Gagal akses folder skills: {e}")
    if action == "list":
        names = sorted(p.stem for p in skills.glob("*.md"))
        return ok(names)
    if action not in ("save", "load"):
        return fail(f"action tidak dikenal: {action} (pakai save|load|list)")
    if not name.strip():
        return fail("`name` wajib diisi untuk save/load.")
    target = skills / f"{_safe_name(name)}.md"
    if action == "save":
        if not content:
            return fail("`content` wajib diisi untuk save.")
        try:
            target.write_text(content, encoding="utf-8")
        except OSError as e:
            return fail(f"Gagal simpan skill: {e}")
        return ok(f"Skill tersimpan: {target}")
    if not target.is_file():
        return fail(f"Skill tidak ditemukan: {name}")
    try:
        return ok(target.read_text(encoding="utf-8"))
    except OSError as e:
        return fail(f"Gagal baca skill: {e}")
