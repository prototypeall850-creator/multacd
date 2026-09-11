"""Chat panel — area percakapan scrollable (user · assistant · tool · error)."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from rich.markdown import Markdown as RichMarkdown
from rich.panel import Panel
from textual.containers import VerticalScroll
from textual.widgets import Markdown, Static

from tui.widgets.tool_activity import ToolActivity


class ChatPanel(VerticalScroll):
    """Kontainer vertikal; tiap pesan di-mount sebagai widget sendiri."""

    LIVE_LINES = 12  # baris live per tool (cukup buat rasa hidup di HP)

    DEFAULT_CSS = """
    ChatPanel .assistant-md {
        border: solid $primary;
        padding: 0 1;
        margin: 1 0;
        height: auto;
    }
    ChatPanel .splash-title {
        text-align: center;
        color: $primary;
        padding: 1 0 0 0;
    }
    ChatPanel .splash-hint {
        text-align: center;
        color: $text-muted;
    }
    ChatPanel .live-out {
        color: $text-muted;
        padding: 0 1;
        height: auto;
    }
    """

    SPLASH_TIPS = (
        "Ketik / lalu pilih command · /model ganti model · /help semua command",
        "Tool baca & git langsung jalan; tulis/shell/web minta izin dulu",
        "Ctrl+T file tree · Ctrl+G diff · Ctrl+R sumber (mode /research)",
    )

    async def show_splash(self, version: str, model: str, mode: str = "code") -> None:
        """Splash v2 (DESIGN §10): logo + model + 1 tip. Sekali saat startup."""
        from tui import icons as _icons
        tip = self.SPLASH_TIPS[0]
        await self.mount(Static(f"[bold]{_icons.icon('app')}  m u l t a c d[/bold]",
                                classes="splash-title"))
        await self.mount(Static(f"{mode} · {model} · v{version}",
                                classes="splash-hint"))
        await self.mount(Static(f"{_icons.icon('bullet')}  Tip  {tip}",
                                classes="splash-hint"))
        self.scroll_end(animate=False)

    def __init__(self) -> None:
        super().__init__(id="chat-panel")
        self._assistant_md: Markdown | None = None
        self._assistant_text = ""
        self._tool_rows: dict[str, ToolActivity] = {}
        self._live: dict[str, tuple[Static, list[str]]] = {}

    async def add_user(self, text: str) -> None:
        await self.mount(Static(Panel(text, title="You", border_style="blue")))
        self.scroll_end(animate=False)

    async def add_info(self, text: str) -> None:
        await self.mount(Static(f"[dim]{text}[/dim]"))
        self.scroll_end(animate=False)

    async def add_error(self, text: str) -> None:
        from tui import icons as _icons
        await self.mount(Static(
            Panel(text, title=f"{_icons.icon('error')} error",
                  border_style="red")))
        self.scroll_end(animate=False)

    async def start_assistant(self) -> None:
        """Mulai bubble assistant baru untuk turn ini (streaming menempel ke sini)."""
        self._assistant_text = ""
        self._assistant_md = Markdown("", classes="assistant-md")
        self._assistant_md.border_title = "multacd"
        await self.mount(self._assistant_md)
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
        """
        entry = self._live.get(call_id)
        if entry is None:
            widget = Static("", classes="live-out")
            await self.mount(widget)
            entry = (widget, [])
            self._live[call_id] = entry
        widget, lines = entry
        lines.append(line[-200:])  # baris super panjang dipotong
        del lines[:-self.LIVE_LINES]
        widget.update("\n".join(lines))
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

    async def clear(self) -> None:
        """Kosongkan semua bubble (dipakai /clear) + reset state streaming."""
        for child in list(self.children):
            await child.remove()
        self._assistant_md = None
        self._assistant_text = ""
        self._tool_rows.clear()

    def render_markdown_text(self, text: str) -> RichMarkdown:
        """Helper (dipakai test): pastikan teks valid buat Rich Markdown."""
        return RichMarkdown(text)
