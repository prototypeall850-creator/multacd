"""Format response untuk Telegram (PLAN Phase 4 Step 4).

Telegram tidak support markdown penuh → kirim plain text yang dibersihkan
(tanpa parse_mode, jadi tidak pernah error parse). Pesan > 4096 dipotong
per batas baris.

Test cepat:
    python -m tg.formatter
"""

from __future__ import annotations

import re
from typing import Any

TG_MAX_MESSAGE = 4096


def _target_of(params: dict[str, Any]) -> str:
    """Target utama: path > command > url > topic > '-' (maks 60 char)."""
    target = (params.get("path") or params.get("command")
              or params.get("url") or params.get("topic") or "-")
    target = str(target)
    return target if len(target) <= 60 else "…" + target[-59:]


def to_telegram(text: str) -> str:
    """Bersihkan markdown LLM jadi plain text yang enak dibaca di HP."""
    if not text:
        return ""
    out = text
    out = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", out)  # gambar → alt
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", out)  # link
    out = re.sub(r"^#{1,6}\s*", "", out, flags=re.M)  # header → teks
    out = re.sub(r"(\*\*|__)(.*?)\1", r"\2", out)  # bold → teks
    out = re.sub(r"(?<!\w)([*_])([^*_\n]+?)\1(?!\w)", r"\2", out)  # it/er
    out = re.sub(r"~~(.*?)~~", r"\1", out)  # strikethrough
    out = re.sub(r"^(\s*)[-*+]\s+", r"\1• ", out, flags=re.M)  # bullet
    out = re.sub(r"^>\s?", "", out, flags=re.M)  # quote
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def split_message(text: str, limit: int = TG_MAX_MESSAGE) -> list[str]:
    """Pecah pesan panjang per batas baris (tidak motong tengah baris)."""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines(keepends=True):
        if size + len(line) > limit and current:
            parts.append("".join(current).rstrip())
            current, size = [], 0
        # Baris tunggal super panjang → potong keras.
        while len(line) > limit:
            parts.append(line[:limit])
            line = line[limit:]
        current.append(line)
        size += len(line)
    if current:
        parts.append("".join(current).rstrip())
    return [p for p in parts if p]


def format_tool_confirm(tool_name: str, params: dict[str, Any]) -> str:
    """Pesan konfirmasi tool: 'Balas Y / N'."""
    return (f"Izin diperlukan:\n{tool_name}  →  {_target_of(params)}\n"
            "Balas: Y untuk izinkan · N untuk tolak")


def format_answer(text: str) -> list[str]:
    """Jawaban akhir agent → list pesan siap kirim."""
    clean = to_telegram(text) or "(kosong — tidak ada jawaban teks)"
    return split_message(clean)


if __name__ == "__main__":
    md = "# Judul\n**tebal** dan *miring* serta [link](https://x.id)\n- item\n> kutip\n```py\nprint(1)\n```"
    plain = to_telegram(md)
    assert "Judul" in plain and "**" not in plain and "*" not in plain
    assert "link (https://x.id)" in plain and "• item" in plain
    assert to_telegram("") == ""

    long = "\n".join(f"baris {i} " + "x" * 50 for i in range(200))
    parts = split_message(long)
    assert len(parts) > 1 and all(len(p) <= TG_MAX_MESSAGE for p in parts)
    for i in (0, 50, 199):
        assert f"baris {i}" in "".join(parts)

    c = format_tool_confirm("write_file", {"path": "src/a.py"})
    assert "write_file" in c and "src/a.py" in c and "Balas: Y" in c

    print("✅ formatter self-test OK (clean + split + confirm)")
