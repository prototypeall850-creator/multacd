"""Slash command palette — ketik / → daftar filter di atas input (DESIGN §7).

    /model      Switch LLM model

> / _                        ← Enter pilih, Tab lengkap, Esc tutup

Navigasi: Up/Down gerak · Enter pilih (submit, kecuali butuh argumen →
autocomplete) · Esc tutup · Tab autocomplete · klik = Enter.
Digerakkan MainScreen (on_text_area_changed) + InputBar (tombol nav).
"""

from __future__ import annotations

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Label, ListItem, ListView, Static

from core.mode_manager import COMMANDS_WITH_ARGS, PALETTE_COMMANDS

MATCH_STYLE = "#b4befe"  # Lavender — highlight bagian yang match


def match_commands(typed: str) -> list[tuple[str, str]]:
    """Filter command by prefix (case-insensitive). Pure function.

    typed = teks setelah '/' sampai spasi pertama. '' → semua.
    """
    needle = typed.strip().lower()
    if not needle:
        return list(PALETTE_COMMANDS)
    return [c for c in PALETTE_COMMANDS if c[0][1:].startswith(needle)]


def render_item(cmd: str, desc: str, needle: str) -> Text:
    """'model' match lavender. Pure function."""
    t = Text()
    t.append(cmd[:1 + len(needle)], style=f"bold {MATCH_STYLE}")
    t.append(cmd[1 + len(needle):])
    t.append(f"      {desc}", style="dim")
    return t


class SlashPalette(Vertical):
    """Popup daftar command. State penuh di sini, aksi via screen/input."""

    def __init__(self) -> None:
        super().__init__(id="slash-palette")
        self._matches: list[tuple[str, str]] = []
        self._index = 0
        self._needle = ""
        self.suppress_next = False  # set saat autocomplete (cukup 1 Changed)

    def compose(self):
        yield Static("commands", id="slash-title")
        yield ListView(id="slash-list")

    @property
    def is_open(self) -> bool:
        return self.display

    @property
    def selected_command(self) -> str | None:
        if not self._matches:
            return None
        return self._matches[self._index][0]

    def open(self, needle: str) -> None:
        self._needle = needle
        self._matches = match_commands(needle)
        self._index = 0
        self._rebuild()
        self.display = True

    def refilter(self, needle: str) -> None:
        if not self.display:
            return
        self.open(needle)

    def close(self) -> None:
        self.display = False
        self._matches = []
        self._index = 0

    def move(self, delta: int) -> None:
        if not self._matches:
            return
        self._index = (self._index + delta) % len(self._matches)
        self._highlight()

    def _rebuild(self) -> None:
        try:
            lst = self.query_one("#slash-list", ListView)
        except Exception:
            return
        lst.clear()
        for cmd, desc in self._matches:
            lst.append(ListItem(Label(render_item(cmd, desc, self._needle))))
        self._highlight()

    def _highlight(self) -> None:
        try:
            lst = self.query_one("#slash-list", ListView)
            if self._matches:
                lst.index = self._index
        except Exception:
            pass

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        try:
            idx = list(self.query_one("#slash-list", ListView).children).index(
                event.item)
            self._index = idx
        except ValueError:
            pass
        screen = self.screen
        if hasattr(screen, "palette_select"):
            screen.palette_select()

    @staticmethod
    def needs_arg(cmd: str) -> bool:
        return cmd in COMMANDS_WITH_ARGS


if __name__ == "__main__":
    assert len(match_commands("")) == len(PALETTE_COMMANDS) == 8
    assert [c for c, _ in match_commands("mo")] == ["/model"]
    assert [c for c, _ in match_commands("R")] == ["/research"]
    assert match_commands("zzz") == []
    t = render_item("/model", "Switch", "mo")
    assert str(t) == "/model      Switch"
    print("✅ slash_palette self-test OK (filter + render)")
