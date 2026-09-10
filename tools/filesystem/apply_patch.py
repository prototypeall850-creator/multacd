"""apply_patch — terapkan unified diff ke file. ASK-REQUIRED."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "apply_patch",
        "description": "Terapkan unified diff (format diff -u) ke satu file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "patch": {"type": "string", "description": "Isi unified diff."},
            },
            "required": ["path", "patch"],
        },
    },
}

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def apply_patch(path: str, patch: str) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.is_file():
        return fail(f"File tidak ditemukan: {path}")
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        return fail(f"Gagal baca {path}: {e}")
    try:
        new_lines = _apply(lines, patch.splitlines())
    except ValueError as e:
        return fail(f"Patch gagal diterapkan: {e}")
    p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return ok(f"Patch diterapkan ke {path}")


def _apply(orig: list[str], patch_lines: list[str]) -> list[str]:
    out: list[str] = []
    i = 0  # cursor di file asli (0-based)
    j = 0
    # Lewati header (--- / +++ / Index: / diff --git)
    while j < len(patch_lines) and not patch_lines[j].startswith("@@"):
        if patch_lines[j].startswith(("---", "+++", "Index:", "diff ")):
            j += 1
        else:
            raise ValueError(f"baris patch tak dikenal: {patch_lines[j]!r}")
    hunks = 0
    while j < len(patch_lines):
        m = _HUNK.match(patch_lines[j])
        if not m:
            raise ValueError(f"hunk header tidak valid: {patch_lines[j]!r}")
        old_start = int(m.group(1)) - 1
        j += 1
        if old_start < i:
            raise ValueError("hunk mundur ke belakang — patch tidak urut")
        out.extend(orig[i:old_start])
        i = old_start
        while j < len(patch_lines) and not patch_lines[j].startswith("@@"):
            line = patch_lines[j]
            j += 1
            if line.startswith(" "):
                if i >= len(orig) or orig[i] != line[1:]:
                    raise ValueError(f"konteks tidak cocok di baris {i + 1}")
                out.append(orig[i])
                i += 1
            elif line.startswith("-"):
                if i >= len(orig) or orig[i] != line[1:]:
                    raise ValueError(f"baris yang dihapus tidak cocok di baris {i + 1}")
                i += 1
            elif line.startswith("+"):
                out.append(line[1:])
            elif line in ("\\ No newline at end of file", ""):
                continue
            else:
                raise ValueError(f"prefix baris patch tidak valid: {line!r}")
        hunks += 1
    if hunks == 0:
        raise ValueError("tidak ada hunk di patch")
    out.extend(orig[i:])
    return out
