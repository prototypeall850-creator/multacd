"""Dialog modal: pertanyaan agent ke user.

NOTE: konfirmasi tool (Y/N/A) pindah ke PermissionPopup (panel tombol di
atas input). File ini tinggal AskDialog.
"""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class AskDialog(ModalScreen[str]):
    """Popup pertanyaan agent → user. Return jawaban (string)."""

    CSS = """
    AskDialog {
        align: center middle;
    }
    AskDialog Container {
        width: 80%;
        max-width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    AskDialog Input {
        width: 100%;
    }
    """

    def __init__(self, question: str, initial: str = "") -> None:
        super().__init__()
        self.question = question
        self.initial = initial

    def compose(self) -> ComposeResult:
        from tui import icons as _icons
        with Container():
            yield Static(f"{_icons.icon('arrow')} {self.question}")
            yield Input(placeholder="ketik jawaban lalu Enter", id="ask-input",
                        value=self.initial)

    def on_mount(self) -> None:
        self.query_one("#ask-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss("(dibatalkan)")


class ContinueDialog(ModalScreen[str]):
    """Batas iterasi tercapai — Lanjut atau Berhenti (ala opencode).

    Return "lanjut" | "berhenti". Enter = lanjut, Esc = berhenti.
    """

    CSS = """
    ContinueDialog {
        align: center middle;
    }
    ContinueDialog Container {
        width: 80%;
        max-width: 60;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    """

    def __init__(self, summary: str, limit: int) -> None:
        super().__init__()
        self.summary = summary
        self.limit = limit

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal
        with Container():
            yield Static(f"[bold]Batas {self.limit} iterasi tercapai[/]\n"
                         f"{self.summary}")
            with Horizontal():
                yield Button("Lanjut (Enter)", id="cont-yes",
                             variant="success")
                yield Button("Berhenti (Esc)", id="cont-no",
                             variant="error")

    def on_mount(self) -> None:
        self.query_one("#cont-yes", Button).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss("lanjut" if event.button.id == "cont-yes" else "berhenti")

    def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.dismiss("lanjut")
        elif event.key == "escape":
            event.prevent_default()
            event.stop()
            self.dismiss("berhenti")
