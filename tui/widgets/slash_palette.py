"""Slash command palette — ketik / → daftar filter di atas input (DESIGN §7).

    /model      Switch LLM model

> / _                        ← Enter pilih, Tab lengkap, Esc tutup

Navigasi: Up/Down gerak · Enter pilih (submit, kecuali butuh argumen →
autocomplete) · Esc tutup · Tab autocomplete · klik = Enter.
Digerakkan MainScreen (on_text_area_changed) + InputBar (tombol nav).
"""

from __future__ import annotations

from contextlib import suppress

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Label, ListItem, ListView, Static

from core.mode_manager import COMMANDS_WITH_ARGS, PALETTE_COMMANDS
from tui.markup_safe import tx_escape as escape
from tui.tokens import rich_color

MATCH_STYLE = "#b4befe"  # Lavender default (theme aktif via rich_color)

# Kategori TUI-side (TUI-R3 §12) — dari 12 command existing, tanpa ubah core.
# Header disisip sebagai item disabled (navigasi skip otomatis).
COMMAND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Mode", ("/code", "/research", "/personal")),
    ("Model & provider", ("/model", "/models", "/connect", "/key", "/base")),
    ("Sesi", ("/clear", "/scan", "/soul", "/help")),
)
GROUP_OF = {cmd: grp for grp, cmds in COMMAND_GROUPS for cmd in cmds}

# Shortcut betulan (binding yang benar ada) — jangan fake (TUI-R3 §12).
COMMAND_KEYS = {"/models": "ctrl+o"}

HEADER_MARK = "##"  # prefix marker item header kategori


def _score(needle: str, name: str) -> int | None:
    """Skor match: 0 prefix, 1 substring, 2 subsequence (fuzzy). None = gagal."""
    if name.startswith(needle):
        return 0
    if needle in name:
        return 1
    it = iter(name)
    if all(ch in it for ch in needle):
        return 2
    return None


def _ranked(needle: str) -> list[tuple[int, str, str]]:
    """(skor, cmd, desc) terurut. Inti match_commands + grouped_matches."""
    needle = needle.strip().lower()
    if not needle:
        return [(0, cmd, desc) for cmd, desc in PALETTE_COMMANDS]
    scored: list[tuple[int, str, str]] = []
    for cmd, desc in PALETTE_COMMANDS:
        s = _score(needle, cmd[1:].lower())
        if s is not None:
            scored.append((s, cmd, desc))
    scored.sort(key=lambda x: (x[0], x[1]))
    return scored


def match_commands(typed: str) -> list[tuple[str, str]]:
    """Filter command fuzzy berperingkat (case-insensitive). Pure function.

    typed = teks setelah '/' sampai spasi pertama. '' → semua.
    Urut: prefix dulu, lalu substring, lalu subsequence. v2 full-bebas:
    '/md' ketemu '/model', 'R' tetap '/research' paling atas.
    """
    return [(c, d) for _, c, d in _ranked(typed)]


def grouped_matches(typed: str) -> list[tuple[str, str]]:
    """Matches + header kategori ('##Grup', ''). Pure function (TUI-R3).

    Tanpa re-skor per grup (ranking fuzzy global dipakai); grup kosong
    disembunyikan. Urutan grup ikut COMMAND_GROUPS.
    """
    items: list[tuple[str, str]] = []
    for grp, _cmds in COMMAND_GROUPS:
        rows = [(c, d) for _, c, d in _ranked(typed)
                if GROUP_OF.get(c) == grp]
        if rows:
            items.append((HEADER_MARK + grp, ""))
            items.extend(rows)
    return items


def is_header(item: tuple[str, str]) -> bool:
    """True kalau item adalah header kategori (bukan command)."""
    return item[0].startswith(HEADER_MARK)


def render_item(cmd: str, desc: str, needle: str,
                accent: str = "#b4befe") -> Text:
    """'model' match accent + shortcut kanan (kalau ada). Pure function.

    accent default hex (selftest/headless); caller widget pass warna theme
    via tokens.rich_color (R12: konsistensi warna single-source).
    """
    t = Text()
    t.append(cmd[:1 + len(needle)], style=f"bold {accent}")
    t.append(cmd[1 + len(needle):])
    t.append(f"      {desc}", style="dim")
    if key := COMMAND_KEYS.get(cmd):
        t.append(f"  ·  {key}", style="dim")
    return t


class SlashPalette(Vertical):
    """Popup daftar command. State penuh di sini, aksi via screen/input."""

    def __init__(self) -> None:
        super().__init__(id="slash-palette")
        self._matches: list[tuple[str, str]] = []
        self._index = 0
        self._needle = ""
        self._overlay = False  # True = dibuka via Ctrl+P (centered overlay)
        self.suppress_next = False  # set saat autocomplete (cukup 1 Changed)

    def compose(self):
        yield Static("commands", id="slash-title")
        yield ListView(id="slash-list")

    @property
    def is_open(self) -> bool:
        return self.display

    @property
    def overlay_open(self) -> bool:
        """Palette mode overlay Ctrl+P (input = search field)."""
        return self.display and self._overlay

    @property
    def selected_command(self) -> str | None:
        if not self._matches:
            return None
        cmd = self._matches[self._index][0]
        return None if is_header((cmd, "")) else cmd

    def open(self, needle: str, overlay: bool = False) -> None:
        self._needle = needle
        self._overlay = overlay
        if overlay:
            self.add_class("overlay")
        self._matches = grouped_matches(needle)
        self._index = self._first_command(0)
        self._rebuild()
        self.display = True

    def refilter(self, needle: str) -> None:
        if not self.display:
            return
        self.open(needle, overlay=self._overlay)

    def close(self) -> None:
        self.display = False
        self._overlay = False
        with suppress(Exception):
            self.remove_class("overlay")
        self._matches = []
        self._index = 0

    def _first_command(self, start: int) -> int:
        """Index command pertama non-header dari start (header di-skip)."""
        i = start
        while i < len(self._matches) and is_header(self._matches[i]):
            i += 1
        return i

    def move(self, delta: int) -> None:
        if not self._matches:
            return
        i = self._index
        for _ in range(len(self._matches)):
            i = (i + delta) % len(self._matches)
            if not is_header(self._matches[i]):
                break
        self._index = i
        self._highlight()

    def _rebuild(self) -> None:
        try:
            lst = self.query_one("#slash-list", ListView)
        except Exception:
            return
        lst.clear()
        if not self._matches:
            lst.append(ListItem(Label(
                f"(tidak ada yang cocok: /{escape(self._needle)})")))
            return
        for cmd, desc in self._matches:
            if is_header((cmd, "")):
                lst.append(ListItem(
                    Label(f"{cmd[len(HEADER_MARK):]}", classes="slash-group"),
                    disabled=True))  # header tak selectable/klik
            else:
                lst.append(ListItem(Label(render_item(
                    cmd, desc, self._needle,
                    rich_color(self.app, "lavender", MATCH_STYLE)))))
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
    assert len(match_commands("")) == len(PALETTE_COMMANDS) == 12
    assert [c for c, _ in match_commands("mo")] == ["/model", "/models"]
    got_r = [c for c, _ in match_commands("R")]
    assert got_r and got_r[0] == "/research"  # fuzzy: prefix menang
    assert [c for c, _ in match_commands("md")] == ["/model", "/models"]  # fuzzy
    assert [c for c, _ in match_commands("ke")] == ["/key"]
    got_m = [c for c, _ in match_commands("mode")]
    assert "/model" in got_m and "/models" in got_m, got_m
    assert [c for c, _ in match_commands("conn")] == ["/connect"]
    assert match_commands("zzz") == []
    t = render_item("/model", "Switch", "mo")
    assert str(t) == "/model      Switch"
    assert "ctrl+o" in str(render_item("/models", "Browse", "mo"))
    assert "ctrl+" not in str(render_item("/model", "Switch", "mo"))
    # TUI-R3: grouping — 12 command + 3 header, ranking global tetap.
    g = grouped_matches("")
    assert len(g) == 15, len(g)
    assert [c for c, _ in g if is_header((c, ""))] == ["##Mode", "##Model & provider", "##Sesi"]
    assert [c for c, _ in grouped_matches("mo") if not is_header((c, ""))] == ["/model", "/models"]
    assert [c for c, _ in grouped_matches("zzz")] == []
    assert is_header(("##Mode", "")) and not is_header(("/model", "x"))
    # Navigasi skip header (konstruktor beneran, tanpa mount).
    pal = SlashPalette()
    pal.open("", overlay=True)
    assert pal.overlay_open is True
    assert pal.selected_command == "/code"
    pal.move(3)  # /code → ... skip header, tetap command
    assert pal.selected_command is not None
    assert not is_header((pal._matches[pal._index][0], ""))
    pal.close()
    assert pal.overlay_open is False and pal._matches == []
    print("✅ slash_palette self-test OK (fuzzy + render + grup)")
