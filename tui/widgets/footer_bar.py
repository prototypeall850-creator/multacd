"""Compact footer TUI-R1 — 1 baris: workdir · usage · hints.

Read-only, tak pernah raise. Angka dari SessionState/context (state
existing) — bukan fake. Layar <70 kolom: hints dipangkas.
"""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from rich.text import Text
from textual.widgets import Static

FULL_HINTS = "ctrl+p commands · ctrl+i panel"
SHORT_HINTS = "ctrl+p · ctrl+i"
BUSY_HINT = "esc batalkan"  # P2 (issue #56): jujur saat turn jalan


def short_workdir(path: str, max_cols: int = 32) -> str:
    """`$HOME/x` → `~/x`. Kepanjangan → potong kiri + '…'. Pure.

    Pakai Path.relative_to (bukan concat string) biar benar di
    Windows yang separatornya backslash (issue #41).
    """
    s = (path or "").strip() or "?"
    with suppress(ValueError, RuntimeError, OSError):
        rel = Path(s).expanduser().relative_to(Path.home())
        s = "~" if str(rel) == "." else f"~/{rel.as_posix()}"
        if len(s) > max_cols >= 2:
            s = "…" + s[-(max_cols - 1):]
        return s
    with suppress(Exception):
        s = str(Path(s).expanduser())
    if len(s) > max_cols >= 2:
        s = "…" + s[-(max_cols - 1):]
    return s


def render_footer(workdir: str, usage: str, compact: bool = False,
                  busy: bool = False) -> str:
    """Satu baris footer. Pure function.

    P2 (issue #56): busy → hints diganti 'esc batalkan' (paling pendek,
    aman di layar sempit; hint binding lain tak relevan saat agent jalan).
    """
    hints = BUSY_HINT if busy else (SHORT_HINTS if compact else FULL_HINTS)
    use = (usage or "").strip() or "—"
    return f"{workdir}  {use}  {hints}"


class FooterBar(Static):
    """Baris paling bawah. Update via set_data (screen), compact via layout."""

    def __init__(self) -> None:
        super().__init__("", id="footer-bar")
        self._workdir = "?"
        self._usage = "—"
        self._compact = False
        self._busy = False  # m2: state instance eksplisit, bukan class attr

    def set_data(self, workdir: str, usage: str) -> None:
        self._workdir = workdir or "?"
        self._usage = usage or "—"
        self._paint()

    def set_busy(self, busy: bool) -> None:
        """P2 (issue #56): turn jalan → hint 'esc batalkan'."""
        if busy != self._busy:
            self._busy = busy
            self._paint()

    def set_compact(self, compact: bool) -> None:
        if compact != self._compact:
            self._compact = compact
            self._paint()

    def _paint(self) -> None:
        text = render_footer(self._workdir, self._usage, self._compact,
                             self._busy)
        with suppress(Exception):  # belum mount saat dipanggil dari test
            self.update(Text(text, style="dim"))


if __name__ == "__main__":
    home = str(Path.home())
    assert short_workdir(home) == "~"
    assert short_workdir(f"{home}/proj") == "~/proj"
    assert short_workdir("") == "?"
    long = short_workdir("/a/" + "x" * 50, 32)
    assert len(long) == 32 and long.startswith("…")
    full = render_footer("~/p", "12.450 · —", False)
    assert "ctrl+i panel" in full and "~/p" in full
    short = render_footer("~/p", "12.450 · —", True)
    assert "ctrl+i panel" not in short and "ctrl+i" in short
    # P2 (issue #56): busy → hint esc, binding lain digantikan.
    busy = render_footer("~/p", "1 · —", False, True)
    assert "esc batalkan" in busy and "ctrl+" not in busy
    busy_c = render_footer("~/p", "1 · —", True, True)
    assert busy_c == busy  # compact-safe: sama pendek di layar sempit
    bar = FooterBar.__new__(FooterBar)
    bar._workdir, bar._usage, bar._compact, bar._busy = "?", "—", False, False
    FooterBar.set_data(bar, "~/p", "1 · —")
    assert bar._workdir == "~/p"
    print("✅ footer_bar self-test OK")
