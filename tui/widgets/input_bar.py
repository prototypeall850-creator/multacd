"""Input bar — box multi-line di bawah. Enter kirim, Shift+Enter newline."""

from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import TextArea

from tui.widgets.model_selector import ModelSelector
from tui.widgets.permission_popup import PermissionPopup
from tui.widgets.slash_palette import SlashPalette


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
        self.border_title = "Enter kirim · /help · Ctrl+O model · Ctrl+I info"

    async def on_key(self, event: events.Key) -> None:
        # Permission bar menunggu → SEMUA tombol jawab jadi miliknya,
        # apapun yang fokus (TextArea menelan keystrokes miliknya sendiri).
        perm = self._waiting_perm()
        if perm is not None and event.key.lower() in (
                "y", "n", "a", "enter", "escape"):
            event.prevent_default()
            event.stop()
            perm.answer_key(event.key)
            return
        pal = self._open_palette()
        sel = self._open_selector()
        if sel is not None:
            # Mode selector: navigasi milik selector, ketikan = filter query.
            if event.key in ("up", "down"):
                event.prevent_default()
                event.stop()
                sel.move(1 if event.key == "down" else -1)
                return
            if event.key == "enter":
                event.prevent_default()
                event.stop()
                self.screen.model_select()
                return
            if event.key == "escape":
                event.prevent_default()
                event.stop()
                sel.close()
                self.clear()
                return
            if event.key == "ctrl+f":
                event.prevent_default()
                event.stop()
                self.screen.model_favorite()
                return
        if pal is not None:
            # Palette terbuka → tombol dinavigasi palette, bukan editing.
            if event.key in ("up", "down"):
                event.prevent_default()
                event.stop()
                pal.move(1 if event.key == "down" else -1)
                return
            if event.key == "enter":
                event.prevent_default()
                event.stop()
                self.screen.palette_select()
                return
            if event.key == "escape":
                event.prevent_default()
                event.stop()
                pal.close()
                return
            if event.key == "tab":
                event.prevent_default()
                event.stop()
                self.screen.palette_autocomplete()
                return
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

    def _open_palette(self) -> SlashPalette | None:
        """Palette yang sedang terbuka (None kalau tidak ada/tutup)."""
        try:
            pal = self.screen.query_one(SlashPalette)
        except Exception:
            return None
        return pal if pal.is_open else None

    def _open_selector(self) -> ModelSelector | None:
        """Model selector yang sedang terbuka (None kalau tutup)."""
        try:
            sel = self.screen.query_one(ModelSelector)
        except Exception:
            return None
        return sel if sel.is_open else None

    def _waiting_perm(self) -> PermissionPopup | None:
        """PermissionPopup yang menunggu jawaban (None kalau tidak ada)."""
        try:
            perm = self.screen.query_one(PermissionPopup)
        except Exception:
            return None
        return perm if perm.is_waiting else None

    def set_busy(self, busy: bool) -> None:
        """Disable saat agent berpikir (hindari submit ganda)."""
        self.disabled = busy
