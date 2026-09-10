"""Dialog modal: pertanyaan agent ke user.

NOTE: konfirmasi tool (Y/N/A) pindah ke PermissionPopup (panel tombol di
atas input). File ini tinggal AskDialog.
"""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class AskDialog(ModalScreen[str]):
    """Popup pertanyaan agent → user. Return jawaban (string)."""

    CSS = """
    AskDialog {
        align: center middle;
    }
    AskDialog Container {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    AskDialog Input {
        width: 100%;
    }
    """

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(f"❓ {self.question}")
            yield Input(placeholder="ketik jawaban lalu Enter", id="ask-input")

    def on_mount(self) -> None:
        self.query_one("#ask-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss("(dibatalkan)")
