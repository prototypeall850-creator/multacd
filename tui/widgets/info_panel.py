"""Info panel kanan — context sesi sekilas (DESIGN §11 v2).

Toggle Ctrl+I, tampil di semua mode. Isi per mode:
- code: project + git + model + sesi
- research: topik + round + sources + model
- personal: daemon + jadwal (disederhanakan: status baris)

Token diestimasi heuristik (chars/4) dan diberi tanda ~ — jujur:
bukan angka resmi provider. Cost tampil '-' kalau tak terlacak.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from textual.containers import Vertical
from textual.widgets import Static


def estimate_tokens(chars: int) -> int:
    """Heuristik kasar: ~4 char per token. Pure function."""
    return max(0, int(chars / 4))


def render_snapshot(data: dict[str, Any]) -> str:
    """Render text panel dari snapshot dict. Pure function (gampang dites)."""
    mode = data.get("mode", "?")
    lines = [f"{data.get('project', '?')}"]
    lines.append("─" * 16)
    if mode == "research":
        lines.append(f"Topik: {data.get('topic', '—')}")
        lines.append(f"Round: {data.get('round', '0/0')}")
        lines.append(f"Sources: {data.get('sources', '0 read')}")
    elif mode == "personal":
        lines.append(f"Daemon: {data.get('daemon', '—')}")
        lines.append(f"Jobs: {data.get('jobs', '—')}")
    else:
        lines.append(f"Git: {data.get('git', '—')}")
    toks = data.get("tokens", 0)
    lines.append(f"Context: ~{toks:,} tokens".replace(",", "."))
    lines.append(f"Session: {data.get('messages', 0)} pesan · "
                 f"{data.get('tools', 0)} tools")
    lines.append(f"Model: {data.get('model', '?')}")
    return "\n".join(lines)


class InfoPanel(Vertical):
    """Panel kanan info. Hidden default, update via snapshot dict."""

    def __init__(self) -> None:
        super().__init__(id="info-panel")
        self._data: dict[str, Any] = {}

    def compose(self):
        yield Static("(info)", id="info-body")

    def update_snapshot(self, data: dict[str, Any]) -> None:
        self._data = dict(data)
        with suppress(Exception):
            self.query_one("#info-body", Static).update(
                render_snapshot(self._data))


if __name__ == "__main__":
    assert estimate_tokens(100) == 25 and estimate_tokens(0) == 0
    s = render_snapshot({"mode": "code", "project": "myapp", "git": "main +3",
                         "tokens": 12450, "messages": 12, "tools": 8,
                         "model": "groq/llama"})
    assert "myapp" in s and "~12.450 tokens" in s and "12 pesan" in s
    r = render_snapshot({"mode": "research", "project": "p", "round": "2/5",
                         "sources": "6 read", "tokens": 0, "messages": 1,
                         "tools": 0, "model": "m"})
    assert "Round: 2/5" in r and "Sources: 6 read" in r
    p = render_snapshot({"mode": "personal", "project": "p", "daemon": "on",
                         "jobs": "2", "tokens": 0, "messages": 0,
                         "tools": 0, "model": "m"})
    assert "Daemon: on" in p
    print("✅ info_panel self-test OK (render 3 mode)")
