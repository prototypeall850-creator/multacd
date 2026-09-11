"""Status bar — 1 baris di atas: nama app · mode · model · status."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from tui import icons


class StatusBar(Static):
    """Contoh: multacd  ·  code  ·  groq/llama-3.3  ·  idle
    (glyph via tui.icons — ikut level nerdfonts/unicode/ascii)."""

    def __init__(self) -> None:
        super().__init__("", id="status-bar")
        self._mode = "coding"
        self._model = "?"
        self._status = "idle"
        self._git = ""

    def set_model(self, model: str) -> None:
        short = model.split("/")[-1]
        self._model = short if len(short) <= 28 else short[:27] + "…"
        self._refresh()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._refresh()

    def set_status(self, status: str) -> None:
        """idle | thinking | waiting (nunggu konfirmasi user)."""
        self._status = status
        self._refresh()

    def set_git(self, summary: dict) -> None:
        """Tampilkan branch + file berubah. Bukan repo → sembunyi (v2).

        DESIGN lama tulis 'no git' — di layar HP itu sampah kolom,
        jadi v2 full-bebas: bukan repo = segmen hilang total.
        """
        if not summary.get("is_repo"):
            self._git = ""
        else:
            parts = [f"{icons.icon('branch')} {summary.get('branch', '?')}"]
            if summary.get("modified"):
                parts.append(f"{icons.icon('modified')}{summary['modified']}")
            if summary.get("untracked"):
                parts.append(f"{icons.icon('added')}{summary['untracked']}")
            self._git = " ".join(parts)
        self._refresh()

    def render_compact(self, max_cols: int = 40) -> str:
        """String ringkas buat Termux: 'multacd · mode · status'.

        Pure (tanpa update widget) — gampang dites + dipakai saat narrow.
        """
        return f"multacd · {self._mode} · {self._status}"[:max_cols]

    def _refresh(self) -> None:
        from tui import tokens as _tok
        dot_color = {"idle": "green", "thinking": "yellow", "waiting": "red"}.get(
            self._status, "green"
        )
        mode_color = {"code": "green", "research": "blue", "personal": "magenta"}.get(
            self._mode, "bold"
        )
        # Termux sempit (<70 kolom): model + git dibuang, sisa esensi.
        compact = _tok.narrow()
        t = Text()
        t.append(f"{icons.icon('app')} multacd", style="bold cyan")
        t.append(f"  ·  {icons.icon('mode')} ", style="dim")
        t.append(self._mode, style=mode_color)
        if not compact:
            t.append("  ·  ", style="dim")
            t.append(self._model, style="magenta")
            if self._git:
                t.append("  ·  ", style="dim")
                t.append(self._git, style="yellow")
        t.append("  ·  ", style="dim")
        dot = {"idle": icons.icon("success"), "thinking": icons.icon("pending"),
               "waiting": icons.icon("warning")}.get(self._status, "●")
        t.append(f"{dot} ", style=f"bold {dot_color}")
        t.append(self._status, style=dot_color)
        self.update(t)
