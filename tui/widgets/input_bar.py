"""Input bar — box multi-line di bawah. Enter kirim, Shift+Enter newline."""

from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import TextArea


class InputSubmitted(Message):
    """Dikirim saat user submit (Enter)."""

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value


class InputBar(TextArea):
    """TextArea yang di-hijack: Enter = kirim, Shift+Enter = newline."""

    def __init__(self) -> None:
        super().__init__("", id="input-bar", language=None)
        self.show_line_numbers = False

    async def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            text = self.text.strip()
            if text and not self.disabled:
                self.clear()
                self.post_message(InputSubmitted(text))
        elif event.key == "shift+enter":
            event.prevent_default()
            event.stop()
            self.insert("\n")

    def set_busy(self, busy: bool) -> None:
        """Disable saat agent berpikir (hindari submit ganda)."""
        self.disabled = busy
