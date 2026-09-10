"""export_research — simpan laporan riset ke .md. ASK-REQUIRED.

Tulis file = operasi WRITE → selalu konfirmasi dulu.
Nama file auto-generate dari topik + timestamp kalau tidak disediakan,
frontmatter YAML metadata selalu ditambahkan.

Test cepat:
    python -m tools.research.export_research
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "export_research",
        "description": (
            "Simpan hasil research ke file markdown dengan frontmatter "
            "metadata (judul, tanggal, provider, jumlah round/sumber)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string",
                            "description": "Isi laporan dalam markdown."},
                "filename": {"type": "string", "default": "",
                             "description": "Nama file (kosong = auto dari title)."},
                "directory": {"type": "string", "default": ".",
                              "description": "Folder output."},
                "title": {"type": "string", "default": "",
                          "description": "Judul laporan (untuk filename + frontmatter)."},
                "provider": {"type": "string", "default": "",
                             "description": "Search provider yang dipakai."},
                "rounds": {"type": "integer", "default": 0,
                           "description": "Jumlah round deep research (1 = quick)."},
                "sources": {"type": "integer", "default": 0,
                            "description": "Jumlah sumber yang dibaca."},
            },
            "required": ["content"],
        },
    },
}


def slugify(text: str, max_len: int = 50) -> str:
    """'Quantum Computing 2025!' → 'quantum-computing-2025'."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:max_len].strip("-") or "research"


def generate_filename(title: str, now: datetime | None = None) -> str:
    """research_{slug}_{YYYYMMDD-HHMM}.md"""
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M")  # local time disengaja (nama file/bacaan manusia)
    return f"research_{slugify(title or 'untitled')}_{stamp}.md"


def add_frontmatter(content: str, title: str = "", provider: str = "",
                    rounds: int = 0, sources: int = 0,
                    now: datetime | None = None) -> str:
    """Tempel YAML header metadata di atas konten."""
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M")  # local time disengaja (nama file/bacaan manusia)
    header = ("---\n"
              f"title: {title or 'Research Report'}\n"
              f"date: {stamp}\n"
              f"provider: {provider or '-'}\n"
              f"rounds: {rounds}\n"
              f"sources: {sources}\n"
              "generated_by: multacd\n"
              "---\n\n")
    return header + content.lstrip("\n")


def export_research(content: str, filename: str = "", directory: str = ".",
                    title: str = "", provider: str = "",
                    rounds: int = 0, sources: int = 0) -> dict[str, Any]:
    if not (content or "").strip():
        return fail("Konten laporan kosong — tidak ada yang disimpan.")
    name = (filename or "").strip() or generate_filename(title or "untitled")
    name = Path(name).name  # cegah path traversal via filename
    if not name.endswith(".md"):
        name += ".md"
    try:
        out_dir = Path(directory or ".")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / name
        path.write_text(
            add_frontmatter(content, title=title, provider=provider,
                            rounds=rounds, sources=sources),
            encoding="utf-8")
    except OSError as e:
        return fail(f"Gagal tulis file: {e}")
    return ok({"file_path": str(path), "filename": name})


if __name__ == "__main__":
    import tempfile

    # 1. slugify
    assert slugify("Quantum Computing Breakthroughs 2025!") == \
        "quantum-computing-breakthroughs-2025"
    assert slugify("  ---  ") == "research"
    assert len(slugify("a" * 100)) <= 50

    # 2. generate_filename pola + timestamp deterministik
    fixed = datetime(2025, 10, 9, 14, 30)
    assert generate_filename("quantum computing breakthroughs 2025",
                             now=fixed) == \
        "research_quantum-computing-breakthroughs-2025_20251009-1430.md"

    # 3. frontmatter lengkap
    md = add_frontmatter("# Isi", title="Judul", provider="tavily",
                         rounds=5, sources=18, now=fixed)
    assert md.startswith("---\ntitle: Judul\ndate: 2025-10-09 14:30\n"
                         "provider: tavily\nrounds: 5\nsources: 18\n"
                         "generated_by: multacd\n---\n\n# Isi"), md[:160]

    # 4. Export roundtrip ke tmp
    tmp = tempfile.mkdtemp(prefix="multacd-export-")
    r = export_research("# Halo", filename="lap", directory=tmp,
                        title="Tes", provider="tavily", rounds=1, sources=2)
    assert r["success"] and r["result"]["filename"] == "lap.md", r
    text = Path(r["result"]["file_path"]).read_text(encoding="utf-8")
    assert "generated_by: multacd" in text and "# Halo" in text

    # 5. Filename auto + path traversal ditolak
    r = export_research("# X", directory=tmp, title="Topik A")
    assert r["success"] and r["result"]["filename"].startswith(
        "research_topik-a_"), r
    r = export_research("# X", filename="../../evil", directory=tmp)
    assert r["success"], r
    assert Path(r["result"]["file_path"]).parent.resolve() == \
        Path(tmp).resolve(), r["result"]

    # 6. Konten kosong → fail; direktori bad → fail jelas
    r = export_research("   ")
    assert not r["success"] and "kosong" in r["error"], r

    print("✅ export_research self-test OK (6 skenario)")
