"""Top session bar TUI-R1 — 1 baris judul sesi (single-title).

Sengaja single-title dulu: tanpa tab palsu / tombol `+` palsu.
Judul = project label sesi (data existing, bukan fake).
"""

from __future__ import annotations

from contextlib import suppress

from rich.text import Text
from textual.widgets import Static


def render_session_title(title: str) -> str:
    """Judul bersih buat bar atas. Pure function."""
    title = (title or "").strip()
    return title if title else "—"


class SessionBar(Static):
    """Baris paling atas: judul sesi kiri. Tinggi 1, tanpa interaksi."""

    def __init__(self, title: str = "") -> None:
        super().__init__("", id="session-bar")
        self._title = render_session_title(title)

    def set_title(self, title: str) -> None:
        self._title = render_session_title(title)
        self._paint()

    def _paint(self) -> None:
        with suppress(Exception):  # belum mount saat dipanggil dari test
            self.update(Text(self._title, style="bold"))


if __name__ == "__main__":
    assert render_session_title("myapp") == "myapp"
    assert render_session_title("  ") == "—"
    assert render_session_title("") == "—"
    bar = SessionBar.__new__(SessionBar)
    bar._title = ""
    SessionBar.set_title(bar, "  myapp  ")
    assert bar._title == "myapp", bar._title
    print("✅ session_bar self-test OK")
