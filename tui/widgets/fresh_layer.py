"""Fresh layer TUI-R13 — tampilan awal ala OpenCode (ref user screenshot).

State awal (belum ada pesan): layar hampir kosong — logo block art di
tengah, input box di tengah (reparent #input-wrap dari MainScreen),
baris kecil workdir + hints di bawah input, footer hanya versi kanan.

Begitu user submit pertama: MainScreen._leave_fresh() reparent input
balik ke #bottom-slot + tampilkan shell normal (top bar, chat, sidebar).
Tanpa sumber MCP/agents → tak ada segmen palsu (hints multacd saja).
"""

from __future__ import annotations

from contextlib import suppress

from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static

# ANSI Shadow, 6 baris per huruf. Hanya huruf "multacd".
_LETTERS: dict[str, tuple[str, ...]] = {
    "m": ("█▀▀▄█▀▀▄", "█  ██  █", "▀▀▀▀▀▀▀▀"),
    "u": ("█  █", "█  █", "▀▀▀▀"),
    "l": ("█ ", "█ ", "▀▀"),
    "t": ("▀▀█▀", "  █ ", "▀▀▀▀"),
    "a": ("█▀▀▄", "█▀▀█", "▀▀▀▀"),
    "c": ("█▀▀▀", "█   ", "▀▀▀▀"),
    "d": ("█▀▀█", "█  █", "▀▀▀▀"),
}

_LOGO_ROWS = 3
# "mult" = m8 + u4 + l2 + t4 + 3 spasi antar-huruf → dua tone di kolom 21.
_SPLIT = 21


def logo_lines(name: str = "multacd") -> list[str]:
    """Block art per baris (pure). Huruf tak dikenal → fallback kosong."""
    if any(ch not in _LETTERS for ch in name):
        return []
    return [" ".join(_LETTERS[ch][r] for ch in name)
            for r in range(_LOGO_ROWS)]


def render_logo(name: str = "multacd") -> Text:
    """Logo dua tone: prefix dim + sisanya terang (pure)."""
    lines = logo_lines(name)
    out = Text()
    for i, line in enumerate(lines):
        if i:
            out.append("\n")
        out.append(line[:_SPLIT], style="dim")
        out.append(line[_SPLIT:], style="bold")
    return out


def render_logo_adaptive(width: int, name: str = "multacd") -> Text:
    """Logo block kalau muat; layar sempit (HP portrait) → teks kecil.

    Block art "multacd" = 56 kolom — di Termux portrait (~50) kepotong.
    """
    lines = logo_lines(name)
    try:
        w = int(width)
    except (TypeError, ValueError):
        w = 0
    if lines and len(lines[0]) <= max(0, w - 4):
        return render_logo(name)
    return Text(name, style="bold")


def fresh_sub_left(workdir: str) -> str:
    """Bagian kiri baris bawah input (pure, markup aman — path statis)."""
    return workdir


def input_meta_text(mode: str, model: str) -> str:
    """Baris meta dalam input box (markup): `code · model` ala OpenCode.

    Mode di-bold (ref frame opencode: 'Build' menonjol). Model dipendekkan
    (tanpa provider prefix — canonical di sidebar/meta jawaban) + dim;
    jangan tampilkan angka palsu.
    """
    from tui.markup_safe import tx_escape as _esc
    short = (model or "?").split("/")[-1][:28] or "?"
    return f"[bold]{_esc(mode)}[/] · [dim]{_esc(short)}[/]"


class FreshScreen(Screen):
    """Layar awal ala OpenCode (TUI-R13): logo + input di tengah.

    Bukan widget layer di MainScreen — Screen terpisah biar transisi
    bersih (push/pop idiomatik Textual, tanpa reparent hack). Submit
    di-forward ke MainScreen._submit via app.submit_from_fresh().
    """

    DEFAULT_CSS = """
    FreshScreen {
        background: $background;
    }
    #fresh-center {
        height: 1fr;
        align: center middle;
    }
    #fresh-block {
        width: 60%;
        max-width: 74;
        height: auto;
        align-horizontal: center;
    }
    #fresh-logo { width: auto; margin-bottom: 2; }
    #fresh-slot {
        width: 100%;
        height: auto;
        border-left: solid $primary;
        border-bottom: solid $primary;
        background: $surface;
        padding: 0 1;
    }
    #fresh-input { height: 3; border: none; background: transparent; }
    #fresh-input-meta { height: 1; }
    #fresh-sub { width: 100%; height: 1; margin-top: 1; }
    #fresh-sub-left { width: 1fr; color: $text-muted; }
    #fresh-sub-right { width: auto; color: $text-muted; }
    #fresh-footer {
        dock: bottom;
        height: 1;
        width: 100%;
        text-align: right;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        from core.session_state import SessionState
        from core.version import get_version
        self._version = get_version()
        self.session = SessionState()  # IDLE — buat TopBar layar ini

    def compose(self):
        from core.codebase import get_git_summary
        from tui.widgets.footer_bar import short_workdir
        from tui.widgets.input_bar import InputBar
        from tui.widgets.status_bar import StatusBar
        yield StatusBar()  # TUI-R13: opencode fresh punya top bar juga
        with Vertical(id="fresh-center"), Vertical(id="fresh-block"):
            yield Static(render_logo_adaptive(self.size.width),
                         id="fresh-logo")
            with Vertical(id="fresh-slot"):
                yield InputBar(id="fresh-input",
                               placeholder="Tanya apa aja…")
                yield Static(input_meta_text(
                    self.app.mode_manager.get_mode(), self.app.cfg.model),
                    id="fresh-input-meta")
            with Horizontal(id="fresh-sub"):
                left = fresh_sub_left(
                    short_workdir(str(self.app.workdir)))
                branch = str(get_git_summary(self.app.workdir)
                             .get("branch") or "")
                if branch:  # ala OpenCode: ~/workdir:branch
                    left = f"{left}:{branch}"
                yield Static(left, id="fresh-sub-left")
                yield Static("enter kirim", id="fresh-sub-right")
        yield Static(self._version, id="fresh-footer")

    def on_mount(self) -> None:
        from tui.widgets.status_bar import StatusBar
        with suppress(Exception):
            bar = self.query_one(StatusBar)
            bar.set_mode(self.app.mode_manager.get_mode())
            bar.render_state(self.session)

    async def on_input_submitted(self, event) -> None:
        """Forward submit ke MainScreen (layar ini pop, lalu _submit)."""
        event.stop()
        self.app.submit_from_fresh(event.value)


if __name__ == "__main__":
    lines = logo_lines()
    assert len(lines) == _LOGO_ROWS
    assert len({len(ln) for ln in lines}) == 1, "lebar baris logo tak konsisten"
    assert len(lines[0]) == 36, len(lines[0])  # m8+u4+l2+t4+a4+c4+d4+6 spasi
    logo = render_logo()
    assert logo.plain.count("\n") == _LOGO_ROWS - 1
    assert len(logo.spans) >= _LOGO_ROWS * 2  # dua tone per baris
    assert logo_lines("opencode!") == []  # huruf tak ada → fallback
    # adaptif: muat → block art; sempit → teks kecil
    assert render_logo_adaptive(100).plain.count("\n") == _LOGO_ROWS - 1
    assert render_logo_adaptive(30).plain == "multacd"
    assert render_logo_adaptive(0).plain == "multacd"  # unknown = aman
    assert "code" in input_meta_text("code", "openai/gpt-5")
    assert "gpt-5" in input_meta_text("code", "openai/gpt-5")
    assert "?" in input_meta_text("code", "")  # model kosong → ? (jangan kosong)
    assert fresh_sub_left("~/p") == "~/p"
    print("✅ fresh_layer self-test OK (logo + adaptif + meta)")
