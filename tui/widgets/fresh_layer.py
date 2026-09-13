"""Fresh layer TUI-R13 — tampilan awal ala OpenCode (ref user screenshot).

State awal (belum ada pesan): layar hampir kosong — logo block art di
tengah, input box di tengah (reparent #input-wrap dari MainScreen),
baris kecil workdir + hints di bawah input, footer hanya versi kanan.

Begitu user submit pertama: MainScreen._leave_fresh() reparent input
balik ke #bottom-slot + tampilkan shell normal (top bar, chat, sidebar).
Tanpa sumber MCP/agents → tak ada segmen palsu (hints multacd saja).
"""

from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static

# ANSI Shadow, 6 baris per huruf. Hanya huruf "multacd".
_LETTERS: dict[str, tuple[str, ...]] = {
    "m": ("███╗   ███╗", "████╗ ████║", "██╔████╔██║",
          "██║╚██╔╝██║", "██║ ╚═╝ ██║", "╚═╝     ╚═╝"),
    "u": ("██╗   ██╗", "██║   ██║", "██║   ██║",
          "██║   ██║", "╚██████╔╝", " ╚═════╝ "),
    "l": ("██╗", "██║", "██║", "██║", "██║", "╚═╝"),
    "t": ("████████╗", "╚══██╔══╝", "   ██║   ",
          "   ██║   ", "   ██║   ", "   ╚═╝   "),
    "a": (" █████╗ ", "██╔══██╗", "███████║",
          "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"),
    "c": (" ██████╗", "██╔════╝", "██║     ",
          "██║     ", "╚██████╗", " ╚═════╝"),
    "d": ("██████╗ ", "██╔══██╗", "██║  ██║",
          "██║  ██║", "██████╔╝", "╚═════╝ "),
}

_LOGO_ROWS = 6
# "mult" = m11+u9+l2+t8 → dua tone split di kolom 30.
_SPLIT = 30


def logo_lines(name: str = "multacd") -> list[str]:
    """Block art per baris (pure). Huruf tak dikenal → fallback kosong."""
    if any(ch not in _LETTERS for ch in name):
        return []
    return ["".join(_LETTERS[ch][r] for ch in name)
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
    """Baris meta dalam input box (pure): `code · model` ala OpenCode.

    Model dipendekkan (tanpa provider prefix — canonical di sidebar/meta
    jawaban); jangan tampilkan angka palsu.
    """
    short = (model or "?").split("/")[-1][:28] or "?"
    return f"{mode} · {short}"


class FreshScreen(Screen):
    """Layar awal ala OpenCode (TUI-R13): logo + input di tengah.

    Bukan widget layer di MainScreen — Screen terpisah biar transisi
    bersih (push/pop idiomatik Textual, tanpa reparent hack). Submit
    di-forward ke MainScreen._submit via app.submit_from_fresh().
    """

    DEFAULT_CSS = """
    FreshScreen {
        background: $background;
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
        background: $surface;
        padding: 0 1;
    }
    #fresh-input { height: 3; border: none; background: transparent; }
    #fresh-input-meta { height: 1; color: $text-muted; }
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
        from core.version import get_version
        self._version = get_version()

    def compose(self):
        from tui.widgets.footer_bar import short_workdir
        from tui.widgets.input_bar import InputBar
        with Vertical(id="fresh-block"):
            yield Static(render_logo_adaptive(self.size.width),
                         id="fresh-logo")
            with Vertical(id="fresh-slot"):
                yield InputBar(id="fresh-input")
                yield Static(input_meta_text(
                    self.app.mode_manager.get_mode(), self.app.cfg.model),
                    id="fresh-input-meta")
            with Horizontal(id="fresh-sub"):
                yield Static(fresh_sub_left(
                    short_workdir(str(self.app.workdir))),
                    id="fresh-sub-left")
                yield Static("enter kirim", id="fresh-sub-right")
        yield Static(self._version, id="fresh-footer")

    async def on_input_submitted(self, event) -> None:
        """Forward submit ke MainScreen (layar ini pop, lalu _submit)."""
        event.stop()
        self.app.submit_from_fresh(event.value)


if __name__ == "__main__":
    lines = logo_lines()
    assert len(lines) == _LOGO_ROWS
    assert len({len(ln) for ln in lines}) == 1, "lebar baris logo tak konsisten"
    assert len(lines[0]) == 56, len(lines[0])  # m11+u9+l2+t8+a8+c8+d8
    logo = render_logo()
    assert logo.plain.count("\n") == _LOGO_ROWS - 1
    assert len(logo.spans) >= 12  # dua tone per baris
    assert logo_lines("opencode!") == []  # huruf tak ada → fallback
    # adaptif: muat → block art; sempit → teks kecil
    assert render_logo_adaptive(100).plain.count("\n") == _LOGO_ROWS - 1
    assert render_logo_adaptive(40).plain == "multacd"
    assert render_logo_adaptive(0).plain == "multacd"  # unknown = aman
    assert input_meta_text("code", "openai/gpt-5") == "code · gpt-5"
    assert input_meta_text("code", "") == "code · ?"
    assert fresh_sub_left("~/p") == "~/p"
    print("✅ fresh_layer self-test OK (logo + adaptif + meta)")
