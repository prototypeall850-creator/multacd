"""Thinking bar — 1 baris tipis antara chat dan input (DESIGN.md §6).

States: idle (baris kosong) · thinking… · running {tool}… ·
searching … · scanning… · running tests…
Animasi titik 1-7 loop tiap 200ms. Warna redup (overlay).

Dipakai MainScreen: thinking saat turn mulai, running X saat tool jalan,
idle saat turn selesai.
"""

from __future__ import annotations

from contextlib import suppress

from rich.text import Text
from textual.widgets import Static

MAX_DOTS = 7
INTERVAL = 0.2

# tool → label khusus (selain ini: "running {tool}...")
TOOL_LABELS = {
    "scan_codebase": "scanning project...",
    "run_tests": "running tests...",
    "run_python": "running script...",
    "web_search": "searching...",
    "web_scrape": "reading page...",
    "quick_research": "researching...",
    "deep_research": "deep researching...",
}


def base_label(state: str) -> str:
    """'thinking' → 'thinking'; tool name → labelnya. Pure function."""
    if state in ("idle", ""):
        return ""
    if state == "thinking":
        return "thinking"
    if state == "waiting":
        return "waiting for approval"
    return TOOL_LABELS.get(state, f"running {state}...")


def dotted(base: str, n_dots: int) -> str:
    """'thinking', 3 → 'thinking...'. Pure function.

    Min-mode (Termux hemat): tanpa titik animasi — hemat reflow/baterai.
    """
    if not base:
        return ""
    try:
        from tui.tokens import should_animate as _anim
        if not _anim():
            return base
    except Exception:
        pass
    if base.endswith("..."):
        base = base[:-3]
    return f"{base}{'.' * n_dots}"


class ThinkingBar(Static):
    """Baris status animasi. show()/hide() dipanggil sync dari MainScreen."""

    def __init__(self) -> None:
        super().__init__("", id="thinking-bar")
        self._base = ""
        self._dots = 1

    def on_mount(self) -> None:
        self.set_interval(INTERVAL, self._tick)

    def show(self, state: str) -> None:
        """state: thinking | waiting | <tool_name>"""
        self._base = base_label(state)
        self._dots = 1
        self._paint()

    def hide(self) -> None:
        self._base = ""
        self._paint()

    @property
    def is_idle(self) -> bool:
        return not self._base

    def _tick(self) -> None:
        if not self._base:
            return
        try:
            from tui.tokens import should_animate as _anim
            if not _anim():
                return  # min-mode: teks statis, tanpa repaint tiap 200ms
        except Exception:
            pass
        self._dots = self._dots % MAX_DOTS + 1
        self._paint()

    def _paint(self) -> None:
        # Plain text (nama tool plugin bisa berisi apa saja) → Text.
        with suppress(Exception):  # belum mount saat show() dari test
            self.update(Text(dotted(self._base, self._dots)))


if __name__ == "__main__":
    assert base_label("idle") == "" and base_label("") == ""
    assert base_label("thinking") == "thinking"
    assert base_label("waiting") == "waiting for approval"
    assert base_label("scan_codebase") == "scanning project..."
    assert base_label("run_tests") == "running tests..."
    assert base_label("web_search") == "searching..."
    assert base_label("bash") == "running bash..."
    assert dotted("thinking", 1) == "thinking."
    assert dotted("thinking...", 7).count(".") == 7
    assert dotted("", 5) == ""
    # Siklus tick 1..7 lalu balik 1
    seq = []
    d = 1
    for _ in range(9):
        seq.append(d)
        d = d % MAX_DOTS + 1
    assert seq == [1, 2, 3, 4, 5, 6, 7, 1, 2], seq
    print("✅ thinking_bar self-test OK (label + dots)")
