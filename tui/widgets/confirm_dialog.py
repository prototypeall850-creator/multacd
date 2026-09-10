"""Dialog modal: konfirmasi tool (Y/N/A) + pertanyaan agent ke user."""

from __future__ import annotations

from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class ConfirmDialog(ModalScreen[str]):
    """Popup Y/N/A saat tool butuh izin. Return 'yes' | 'no' | 'all'."""

    CSS = """
    ConfirmDialog {
        align: center middle;
    }
    ConfirmDialog Container {
        width: 60;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    ConfirmDialog Static {
        width: 100%;
    }
    """

    def __init__(self, tool_name: str, params: dict[str, Any]) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.params = params

    def compose(self) -> ComposeResult:
        target = self.params.get("path") or self.params.get("command") or self.params.get("url") or "-"
        with Container():
            yield Static("⚠️  Konfirmasi Diperlukan", classes="title")
            yield Static(f"Tool   : {self.tool_name}")
            yield Static(f"Target : {target}")
            yield Static("")
            yield Static("[Y] Izinkan   [N] Tolak   [A] Izinkan Semua Sesi Ini")
            yield Button("Izinkan [Y]", id="btn-yes", variant="success")
            yield Button("Tolak [N]", id="btn-no", variant="error")
            yield Button("Semua [A]", id="btn-all", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss({"btn-yes": "yes", "btn-no": "no", "btn-all": "all"}[event.button.id])

    def on_key(self, event: events.Key) -> None:
        key = event.key.lower()
        if key == "y":
            self.dismiss("yes")
        elif key in ("n", "escape"):
            self.dismiss("no")
        elif key == "a":
            self.dismiss("all")


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
