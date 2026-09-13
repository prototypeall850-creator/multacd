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

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Static


def estimate_tokens(chars: int) -> int:
    """Heuristik kasar: ~4 char per token. Pure function."""
    return max(0, int(chars / 4))


def render_snapshot(data: dict[str, Any]) -> str:
    """Render text panel dari snapshot dict. Pure function (gampang dites).

    Section ikut TUI_REDESIGN §20: Session/Context/Usage/Agent + mode/git
    + MCP (di-render ContextSidebar, bukan di sini). Tanpa sumber limit
    konteks/MCP registry → persen/limit/server TAK ditampilkan (jangan
    fake angka); yang tampil hanya yang benar ada.
    """
    mode = data.get("mode", "?")
    lines = [f"{data.get('project', '?')}"]
    lines.append("─" * 16)
    lines.append(f"Session: {data.get('messages', 0)} pesan · "
                 f"{data.get('tools', 0)} tools")
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
    # int = estimasi (kasih ~); str = sudah diformat caller (resmi provider).
    toks_s = f"~{toks:,}".replace(",", ".") if isinstance(toks, int) else str(toks)
    lines.append(f"Context: {toks_s} tokens")
    prompt = data.get("prompt", 0)
    comp = data.get("completion", 0)
    prompt_s = f"~{prompt:,}".replace(",", ".") if isinstance(prompt, int) else str(prompt)
    comp_s = f"~{comp:,}".replace(",", ".") if isinstance(comp, int) else str(comp)
    lines.append(f"In: {prompt_s} · Out: {comp_s}")
    lines.append(f"Cost: {data.get('cost', '—')}")
    lines.append(f"Agent: {mode} · {data.get('model', '?')} · "
                 f"{data.get('status', 'idle')}")
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
                Text(render_snapshot(self._data)))


if __name__ == "__main__":
    assert estimate_tokens(100) == 25 and estimate_tokens(0) == 0
    s = render_snapshot({"mode": "code", "project": "myapp", "git": "main +3",
                         "tokens": 12450, "messages": 12, "tools": 8,
                         "model": "groq/llama"})
    assert "myapp" in s and "~12.450 tokens" in s and "12 pesan" in s
    assert "Cost: —" in s
    s2 = render_snapshot({"mode": "code", "project": "p", "git": "g",
                          "tokens": "12.450", "prompt": "10.000",
                          "completion": "2.450", "messages": 1, "tools": 0,
                          "model": "m", "status": "idle"})
    ctx_line = s2.split("Context:")[1].split("\n")[0]
    assert "Context: 12.450 tokens" in s2 and "~" not in ctx_line
    assert "In: 10.000 · Out: 2.450" in s2
    r = render_snapshot({"mode": "research", "project": "p", "round": "2/5",
                         "sources": "6 read", "tokens": 0, "messages": 1,
                         "tools": 0, "model": "m"})
    assert "Round: 2/5" in r and "Sources: 6 read" in r
    p = render_snapshot({"mode": "personal", "project": "p", "daemon": "on",
                         "jobs": "2", "tokens": 0, "messages": 0,
                         "tools": 0, "model": "m"})
    assert "Daemon: on" in p
    # TUI-R5: Usage split + status agent (data SessionState, bukan fake).
    u = render_snapshot({"mode": "code", "project": "p", "git": "g",
                         "tokens": "1.200", "prompt": 1000, "completion": 200,
                         "cost": "$0.003 est", "messages": 4, "tools": 2,
                         "model": "groq/x", "status": "thinking"})
    assert "In: ~1.000 · Out: ~200" in u, u
    assert "Agent: code · groq/x · thinking" in u, u
    assert "Session: 4 pesan · 2 tools" in u
    print("✅ info_panel self-test OK (render 3 mode + usage/agent)")
