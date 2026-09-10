"""Chat panel — area percakapan scrollable (user · assistant · tool · error)."""

from __future__ import annotations

from typing import Any

from rich.markdown import Markdown as RichMarkdown
from rich.panel import Panel
from textual.containers import VerticalScroll
from textual.widgets import Markdown, Static


class ChatPanel(VerticalScroll):
    """Kontainer vertikal; tiap pesan di-mount sebagai widget sendiri."""

    DEFAULT_CSS = """
    ChatPanel .assistant-md {
        border: solid green;
        padding: 0 1;
        margin: 1 0;
        height: auto;
    }
    """

    def __init__(self) -> None:
        super().__init__(id="chat-panel")
        self._assistant_md: Markdown | None = None
        self._assistant_text = ""
        self._tool_rows: dict[str, Static] = {}

    async def add_user(self, text: str) -> None:
        await self.mount(Static(Panel(text, title="You", border_style="blue")))
        self.scroll_end(animate=False)

    async def add_info(self, text: str) -> None:
        await self.mount(Static(f"[dim]{text}[/dim]"))
        self.scroll_end(animate=False)

    async def add_error(self, text: str) -> None:
        await self.mount(Static(Panel(text, title="⚠️ error", border_style="red")))
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
        target = params.get("path") or params.get("command") or params.get("url") or ""
        target = str(target)
        if len(target) > 60:
            target = "…" + target[-59:]
        row = Static(f"🔧 [bold]{name}[/bold] · {target} ··· ⏳", id=f"tool-{call_id}")
        self._tool_rows[call_id] = row
        await self.mount(row)
        self.scroll_end(animate=False)

    async def update_tool_row(self, call_id: str, name: str, success: bool) -> None:
        row = self._tool_rows.pop(call_id, None)
        if row is None:
            return
        mark = "✅" if success else "❌"
        row.update(f"🔧 [bold]{name}[/bold] ····· {mark}")

    def render_markdown_text(self, text: str) -> RichMarkdown:
        """Helper (dipakai test): pastikan teks valid buat Rich Markdown."""
        return RichMarkdown(text)
