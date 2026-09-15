"""Chat panel — area percakapan scrollable (user · assistant · tool · error)."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from rich.markdown import Markdown as RichMarkdown
from rich.panel import Panel
from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import Markdown, Static

from tui.markup_safe import tx_escape as escape
from tui.tokens import rich_color
from tui.widgets.tool_activity import ToolActivity


def render_meta(mode: str, model: str, secs: float, tok: int) -> str:
    """Meta kecil di bawah jawaban (TUI-R2 §7). Pure function.

    `mode · model · 4.7s · 101.1 tok/s` — tok/s hanya kalau provider
    melapor usage (tok>0); jangan fake angka.
    """
    short = (model or "?").split("/")[-1][:28] or "?"
    base = f"{mode} · {short} · {max(0.0, secs):.1f}s"
    if tok > 0 and secs > 0:
        base += f" · {tok / secs:.1f} tok/s"
    return base


class ChatPanel(VerticalScroll):
    """Kontainer vertikal; tiap pesan di-mount sebagai widget sendiri."""

    LIVE_LINES = 6  # baris live per tool (§14: compact; penuhnya di expanded)

    DEFAULT_CSS = """
    ChatPanel .assistant-md {
        padding: 0 1;
        margin: 1 0;
        height: auto;
    }
    ChatPanel .user-msg {
        border-left: solid $primary;
        padding: 0 1;
        margin: 0 0 1 0;
        height: auto;
    }
    ChatPanel .assistant-meta {
        text-align: left;
        color: $text-muted;
        margin: 0 0 1 0;
    }
    ChatPanel .splash-logo {
        text-align: center;
        color: $text;
        padding: 2 0 1 0;
    }
    ChatPanel .splash-body {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }
    ChatPanel .splash-ver {
        text-align: right;
        color: $text-muted;
    }
    ChatPanel .live-out {
        color: $text-muted;
        border-left: solid $primary;
        background: $surface;
        margin-left: 2;
        padding: 0 1;
        height: auto;
    }
    """

    SPLASH_QUOTE = '"Perbaiki tests rusak"'

    # Tips bergantian (§10: bullet peach). Isi = binding betulan, bukan janji.
    SPLASH_TIPS = (
        "Ketik /connect untuk setup provider",
        "Ketik / lalu pilih command · ctrl+o ganti model",
        "Ctrl+t file tree · ctrl+g diff · ctrl+r sumber research",
    )

    @staticmethod
    def pick_tip(rng=None) -> str:
        """Satu tip acak (R7). rng di-inject biar test deterministik."""
        import random as _random
        return (rng or _random).choice(ChatPanel.SPLASH_TIPS)

    async def show_splash(self, version: str, model: str, mode: str = "code") -> None:
        """Splash §10 (logo spaced + panel prompt + tip + versi). Sekali saat startup."""
        from tui import icons as _icons
        short = model.split("/")[-1][:28] or "?"
        try:
            from core.providers import provider_id_of
            prov = provider_id_of(model) or "custom"
        except Exception:
            prov = "custom"
        logo = Text("m u l t a c d",
                    style=f"bold {rich_color(self.app, 'lavender', '#b4befe')}")  # §10
        body = Text()
        body.append("Tanya apapun... ", style="")
        body.append(self.SPLASH_QUOTE, style="dim")
        body.append("\n")
        body.append(mode, style="blue")
        body.append(f"  ·  {short}  ·  {prov}", style="dim")
        tip = Text()
        tip.append(f"{_icons.icon('bullet')}  Tip  ",
                   style=rich_color(self.app, "peach", "#fab387"))  # §10
        tip.append(self.pick_tip(), style="dim")
        ver = Text(f"v{version}", style="dim")
        # TUI-R7: tanpa Panel border (§34) + tanpa hints (duplikat footer).
        widgets = [
            Static(logo, classes="splash-logo"),
            Static(body, classes="splash-body"),
            Static(tip),
            Static(ver, classes="splash-ver"),
        ]
        for w in widgets:
            await self.mount(w)
        self._splash = widgets
        self.scroll_end(animate=False)

    async def dismiss_splash(self) -> None:
        """Hapus splash saat user mulai turn pertama (§10: transisi ke layout normal).

        Info welcome (plugin/project) bukan splash — tetap tampil.
        """
        for w in getattr(self, "_splash", []):
            with suppress(Exception):
                if w.parent is not None:
                    await w.remove()
        self._splash = []

    def __init__(self) -> None:
        super().__init__(id="chat-panel")
        self._assistant_md: Markdown | None = None
        self._assistant_text = ""
        self._assistant_history: list[str] = []  # jawaban selesai (buat /copy)
        self._tool_rows: dict[str, ToolActivity] = {}
        self._live: dict[str, tuple[Static, list[str]]] = {}
        self._splash: list = []  # widget splash §10 (dismiss saat turn pertama)

    async def add_user(self, text: str) -> None:
        # Aksen kiri tipis (TUI-R2 §7) — tanpa card/title "You" besar.
        # Body dibungkus Text: user bisa ketik `[...]` seenaknya
        # tanpa dianggap markup (issue #29).
        await self.mount(Static(Text(text), classes="user-msg"))
        self.scroll_end(animate=False)

    async def add_info(self, text: str) -> None:
        await self.mount(Static(f"[dim]{escape(text)}[/dim]"))
        self.scroll_end(animate=False)

    async def add_error(self, text: str) -> None:
        from tui import icons as _icons
        await self.mount(Static(
            Panel(Text(text), title=f"{_icons.icon('error')} error",
                  border_style="red")))
        self.scroll_end(animate=False)

    async def start_assistant(self) -> None:
        """Mulai area assistant baru untuk turn ini (streaming menempel)."""
        self._assistant_text = ""
        self._assistant_md = Markdown("", classes="assistant-md")
        await self.mount(self._assistant_md)
        self.scroll_end(animate=False)

    async def close_assistant(self, meta: str = "") -> None:
        """Tutup turn: history di-push + meta kecil (§7). Aman kalau kosong.

        Push history pindah ke sini (dulu di start_assistant turn berikut)
        — isi history identik, cuma timing lebih awal.
        """
        if self._assistant_md is None:
            return
        if self._assistant_text.strip():
            self._assistant_history.append(self._assistant_text)
            del self._assistant_history[:-20]
        self._assistant_md = None
        if meta.strip():
            await self.mount(Static(Text(meta.strip()),
                                    classes="assistant-meta"))
            self.scroll_end(animate=False)

    async def append_assistant_text(self, delta: str) -> None:
        self._assistant_text += delta
        if self._assistant_md is not None:
            await self._assistant_md.update(self._assistant_text)
        self.scroll_end(animate=False)

    async def add_tool_row(self, call_id: str, name: str, params: dict[str, Any]) -> None:
        row = ToolActivity(call_id, name, params)
        self._tool_rows[call_id] = row
        await self.mount(row)
        self.scroll_end(animate=False)

    async def add_live_output(self, call_id: str, line: str) -> None:
        """Tempel baris live output tool (update widget yang sama per call).

        Dipanggil dari thread worker via call_from_thread + run_worker.
        Max LIVE_LINES terakhir; widget dibuang saat tool done.

        m-D (ronde-2 audit): worker ini fire-and-forget — guard M5 di
        _queue_live dievaluasi saat ENQUEUE; baris telat bisa mount
        setelah cancel/done → cek ulang di sini: call tanpa row tool =
        artefak, buang senyap (bukan blok live yatim).

        MINOR-3 (audit final): row done/cancelled juga senyap — baris
        telat pasca-AgentToolDone jangan hidupkan lagi blok live.
        """
        row = self._tool_rows.get(call_id)
        if row is None or row._done:
            return
        entry = self._live.get(call_id)
        fresh = entry is None
        if fresh:
            widget = Static("", classes="live-out")
            entry = (widget, [])
            # MAJOR-2 (audit final): daftarkan SEBELUM await mana pun —
            # dua baris burst sama-sama lihat None → dobel-mount, widget
            # pertama yatim permanen + urutan baris tertukar.
            self._live[call_id] = entry
        widget, lines = entry
        # Append+update tanpa await (atomik) — urutan baris burst terjaga.
        lines.append(line[-200:])  # baris super panjang dipotong
        del lines[:-self.LIVE_LINES]
        # Output tool mentah (bisa berisi `[...]`) → Text, bukan markup.
        widget.update(Text("\n".join(lines)))
        if fresh:
            await self.mount(widget)
        self.scroll_end(animate=False)

    async def add_diff_preview(self, workdir: str = ".") -> None:
        """Preview diff otomatis (#4) — tampil sebelum dialog approve commit."""
        from tools.git.git_diff import git_diff
        from tui.widgets.diff_viewer import render_diff
        try:
            res = await asyncio.to_thread(git_diff, workdir)
        except Exception:
            return
        if not res.get("success"):
            return
        text = str(res.get("result", ""))
        head = Text("diff preview — cek sebelum approve:", style="dim")
        if not text.strip() or text.strip() == "(tidak ada output)":
            await self.mount(Static(head))
            await self.mount(Static("(tidak ada perubahan buat di-commit)"))
        else:
            await self.mount(Static(head))
            await self.mount(Static(render_diff(text)))
        self.scroll_end(animate=False)

    async def drop_live_output(self, call_id: str) -> None:
        """Buang widget live (hasil penuh sudah di ToolActivity)."""
        entry = self._live.pop(call_id, None)
        if entry is not None:
            with suppress(Exception):
                await entry[0].remove()

    async def update_tool_row(self, call_id: str, name: str, success: bool,
                              result: dict[str, Any] | None = None) -> None:
        _ = name
        row = self._tool_rows.get(call_id)
        if row is None:
            return
        row.set_done(success, result)

    def mark_tool_cancelled(self, call_id: str) -> None:
        """P2 (issue #56): row tool masih running → cancelled (Esc)."""
        row = self._tool_rows.get(call_id)
        if row is not None:
            row.set_cancelled()

    def assistant_history(self, n: int = 1) -> str:
        """Jawaban assistant ke-n dari belakang (1 = terakhir). '' = kosong."""
        if n < 1:
            return ""
        idx = len(self._assistant_history) - n
        if idx < 0:
            # Turn berjalan (belum start berikutnya) = kandidat terakhir.
            if n == 1 and self._assistant_text.strip():
                return self._assistant_text
            return ""
        return self._assistant_history[idx]

    async def clear(self) -> None:
        """Kosongkan semua bubble (dipakai /clear) + reset state streaming."""
        for child in list(self.children):
            await child.remove()
        self._splash = []
        self._assistant_md = None
        self._assistant_text = ""
        self._assistant_history.clear()
        self._tool_rows.clear()
        # m-B: widget live sudah kebuang bareng children di atas — dict-nya
        # wajib direset juga, kalau tidak add_live_output berikutnya update
        # widget yatim yang sudah lepas dari DOM.
        self._live.clear()

    def render_markdown_text(self, text: str) -> RichMarkdown:
        """Helper (dipakai test): pastikan teks valid buat Rich Markdown."""
        return RichMarkdown(text)
