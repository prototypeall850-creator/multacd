"""Todo source — baca item belum selesai (PLAN Phase 4 Step 7).

Cari: ./todo.md, ./TODO.md, ~/.multacd/todo.md (hormati MULTACD_HOME).
Format: '- [ ] x' / '- x' / '* x' / '1. x'. Selesai ([x]/[X]) di-skip.

Test cepat:
    python -m briefing.sources.todo_source
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_DONE_RE = re.compile(r"^\s*[-*]\s*\[[xX]\]\s*")
_ITEM_RE = re.compile(r"^\s*(?:[-*]\s*(?:\[[ ]\]\s*)?|\d+[.)]\s*)(.+?)\s*$")


def find_todo_files(extra: list[str | Path] | None = None) -> list[Path]:
    """Kembalikan path todo yang ada (tidak raise kalau kosong)."""
    candidates = [Path("todo.md"), Path("TODO.md"),
                  Path(os.environ.get("MULTACD_HOME", str(Path.home())))
                  / ".multacd" / "todo.md"]
    if extra:
        candidates.extend(Path(p) for p in extra)
    return [p for p in candidates if p.is_file()]


def parse_todo_file(path: str | Path) -> list[str]:
    """Parse item belum selesai dari satu file."""
    items: list[str] = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip() or _DONE_RE.match(line):
            continue
        m = _ITEM_RE.match(line)
        if m and m.group(1).strip():
            items.append(m.group(1).strip())
    return items


def get_todos(extra: list[str | Path] | None = None) -> list[str]:
    """Semua todo pending dari semua file yang ketemu."""
    out: list[str] = []
    for path in find_todo_files(extra):
        out.extend(parse_todo_file(path))
    return out


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        os.environ["MULTACD_HOME"] = d
        assert get_todos() == []  # tidak ada file → kosong, bukan error
        f = Path(d) / "todo.md"
        f.write_text("# Hari ini\n- [ ] Fix bug agent\n- [x] Sudah ini\n"
                     "- Beli susu\n1. Review PR\n", encoding="utf-8")
        items = get_todos(extra=[f])
        assert "Fix bug agent" in items and "Beli susu" in items
        assert "Review PR" in items
        assert not any("Sudah ini" in i for i in items)
        del os.environ["MULTACD_HOME"]

    print("✅ todo_source self-test OK (parse + skip-done)")
