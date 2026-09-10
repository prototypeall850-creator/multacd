"""Status bar — 1 baris di atas: nama app · mode · model · status."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static


class StatusBar(Static):
    """Contoh: ⚡ multacd  ·  💻 coding  ·  groq/llama-3.3  ·  ● idle"""

    def __init__(self) -> None:
        super().__init__("", id="status-bar")
        self._mode = "coding"
        self._model = "?"
        self._status = "idle"

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

    def _refresh(self) -> None:
        dot_color = {"idle": "green", "thinking": "yellow", "waiting": "red"}.get(
            self._status, "green"
        )
        t = Text()
        t.append("⚡ multacd", style="bold cyan")
        t.append("  ·  💻 ", style="dim")
        t.append(self._mode, style="bold")
        t.append("  ·  ", style="dim")
        t.append(self._model, style="magenta")
        t.append("  ·  ", style="dim")
        t.append("● ", style=f"bold {dot_color}")
        t.append(self._status, style=dot_color)
        self.update(t)
