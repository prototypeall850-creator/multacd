"""Top bar TUI-R7 — SATU baris tipis: app · session · mode · status.

Recompose dari SessionBar+StatusBar lama: identity + session + mode +
status dot. Model/git/token punya tempat lain (sidebar + meta jawaban)
— §5 TUI_REDESIGN_V2: jangan numpuk di top.
"""

from __future__ import annotations

from contextlib import suppress

from rich.text import Text
from textual.widgets import Static

from tui import icons


def agent_status_for(status: object) -> str:
    """Mapping murni AgentStatus → segmen status bar (R5, headless testable).

    idle → "idle" · thinking/executing → "thinking" · nunggu → "waiting".
    """
    from core.session_state import AgentStatus as _S
    if status in (_S.WAITING_PERMISSION, _S.WAITING_USER):
        return "waiting"
    if status in (_S.THINKING, _S.EXECUTING_TOOL):
        return "thinking"
    return "idle"


def render_session_title(title: str, max_cols: int = 24) -> str:
    """Judul sesi bersih + potong kalau kepanjangan. Pure function."""
    title = (title or "").strip()
    if not title:
        return "—"
    return title if len(title) <= max_cols else title[:max_cols - 1] + "…"


class TopBar(Static):
    """Baris paling atas: `● multacd · <judul> · <mode> · ● <status>`."""

    def __init__(self) -> None:
        super().__init__("", id="top-bar")
        self._title = ""
        self._mode = "coding"
        self._status = "idle"

    def set_title(self, title: str) -> None:
        self._title = render_session_title(title)
        self._refresh()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._refresh()

    def set_status(self, status: str) -> None:
        """idle | thinking | waiting (nunggu konfirmasi user)."""
        self._status = status
        self._refresh()

    def render_state(self, state) -> None:
        """Status agent dari SessionState (R5) — screen tak set manual lagi.

        `state` bertipe SessionState (tanpa annotation import biar ringan).
        """
        self.set_status(agent_status_for(state.status))

    def render_compact(self, max_cols: int = 40) -> str:
        """String ringkas buat Termux: 'multacd · mode · status'. Pure."""
        return f"multacd · {self._mode} · {self._status}"[:max_cols]

    def _refresh(self) -> None:
        from tui import tokens as _tok
        dot_color = {"idle": "green", "thinking": "yellow", "waiting": "red"}.get(
            self._status, "green"
        )
        mode_color = {"code": "green", "research": "blue", "personal": "magenta"}.get(
            self._mode, "bold"
        )
        t = Text()
        t.append(f"{icons.icon('app')} multacd", style="bold cyan")
        t.append(f"  ·  {self._title}", style="bold")
        t.append(f"  ·  {icons.icon('mode')} ", style="dim")
        t.append(self._mode, style=mode_color)
        if not _tok.narrow():
            t.append("  ·  ", style="dim")
            dot = {"idle": icons.icon("success"), "thinking": icons.icon("pending"),
                   "waiting": icons.icon("warning")}.get(self._status, "●")
            t.append(f"{dot} ", style=f"bold {dot_color}")
            t.append(self._status, style=dot_color)
        with suppress(Exception):  # belum mount saat dipanggil dari test
            self.update(t)


# Kompat: nama lama dipakai main_screen + test (R5). Alias ke TopBar.
StatusBar = TopBar


if __name__ == "__main__":
    from core.session_state import AgentStatus as _S
    assert agent_status_for(_S.IDLE) == "idle"
    assert agent_status_for(_S.THINKING) == "thinking"
    assert agent_status_for(_S.EXECUTING_TOOL) == "thinking"
    assert agent_status_for(_S.WAITING_PERMISSION) == "waiting"
    assert agent_status_for(_S.WAITING_USER) == "waiting"
    assert TopBar().render_compact().startswith("multacd")
    assert render_session_title("myapp") == "myapp"
    assert render_session_title("") == "—"
    assert render_session_title("  ") == "—"
    assert len(render_session_title("x" * 40)) == 24
    bar = TopBar.__new__(TopBar)
    bar._title = bar._mode = bar._status = ""
    TopBar.set_title(bar, "  myapp  ")
    assert bar._title == "myapp", bar._title
    TopBar.set_status(bar, "thinking")
    assert bar._status == "thinking"
    print("✅ status_bar self-test OK (top bar + mapping + compact)")
