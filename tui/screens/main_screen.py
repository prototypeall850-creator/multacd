"""Layar utama: status_bar + chat_panel + input_bar, tersambung ke agent_loop."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen

from core.agent_loop import (
    AgentDone,
    AgentError,
    AgentText,
    AgentToolDone,
    AgentToolStart,
    run_agent,
)
from tui.widgets.chat_panel import ChatPanel
from tui.widgets.confirm_dialog import AskDialog, ConfirmDialog
from tui.widgets.input_bar import InputBar, InputSubmitted
from tui.widgets.status_bar import StatusBar


class MainScreen(Screen):
    """Susun widget + handle event dari agent_loop."""

    CSS = """
    MainScreen {
        layout: vertical;
    }
    #status-bar {
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    #chat-panel {
        height: 1fr;
        padding: 0 1;
    }
    #input-bar {
        height: 5;
        border: solid $primary;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        # NOTE: jangan pakai nama `_running` — itu atribut internal
        # Textual MessagePump (dioverwrite framework saat pump start).
        self._turn_running = False

    def compose(self) -> ComposeResult:
        yield StatusBar()
        yield ChatPanel()
        yield InputBar()

    def on_mount(self) -> None:
        bar = self.query_one(StatusBar)
        bar.set_model(self.app.cfg.model)
        bar.set_mode(self.app.mode_manager.get_mode())
        bar.set_status("idle")
        self.query_one(InputBar).focus()
        self.run_worker(self._show_welcome())

    async def _show_welcome(self) -> None:
        chat = self.query_one(ChatPanel)
        await chat.add_info(
            f"⚡ Selamat datang di multacd v{self.app.version} — model: {self.app.cfg.model}\n"
            f"📁 {self.app.project_label}\n"
            "Ketik pesan lalu Enter untuk kirim · Shift+Enter untuk newline · Ctrl+C keluar.\n"
            "Tool baca & git langsung jalan; tulis/shell/web minta izin [Y/N/A] dulu.\n"
            "Ketik /help buat daftar command."
        )

    def _sync_mode_ui(self) -> None:
        """Samakan status bar + composer dengan mode/model aktif."""
        mm = self.app.mode_manager
        bar = self.query_one(StatusBar)
        bar.set_mode(mm.get_mode())
        bar.set_model(self.app.cfg.model)
        self.app.composer.update_mode(mm.get_mode_prompt())

    async def on_input_submitted(self, event: InputSubmitted) -> None:
        if self._turn_running:
            return  # abaikan submit ganda saat agent berpikir
        self._turn_running = True
        self.run_worker(self._run_turn(event.value))

    async def _run_turn(self, text: str) -> None:
        chat = self.query_one(ChatPanel)
        bar = self.query_one(StatusBar)
        inbar = self.query_one(InputBar)
        try:
            inbar.set_busy(True)
            bar.set_status("thinking")
            # /clear: bersihkan UI dulu biar command + respons tetap kelihatan.
            # (Single source of truth parsing tetap ModeManager di agent_loop.)
            stripped = text.strip().lower()
            if stripped == "/clear" or stripped.startswith("/clear "):
                await chat.clear()
            await chat.add_user(text)
            await chat.start_assistant()
            async for event in run_agent(
                text,
                self.app.context,
                self.app.cfg,
                llm_client=self.app.llm_client,
                confirm=self._confirm,
                ask_user=self._ask_user,
                mode_manager=self.app.mode_manager,
            ):
                if isinstance(event, AgentText):
                    await chat.append_assistant_text(event.delta)
                elif isinstance(event, AgentToolStart):
                    await chat.add_tool_row(event.call_id, event.name, event.params)
                elif isinstance(event, AgentToolDone):
                    await chat.update_tool_row(event.call_id, event.name, event.success)
                elif isinstance(event, AgentDone):
                    pass  # teks sudah ter-stream penuh
                elif isinstance(event, AgentError):
                    await chat.add_error(event.message)
        finally:
            self._sync_mode_ui()
            bar.set_status("idle")
            inbar.set_busy(False)
            inbar.focus()
            self._turn_running = False

    async def _confirm(self, tool_name: str, params: dict[str, Any]) -> str:
        bar = self.query_one(StatusBar)
        bar.set_status("waiting")
        try:
            # wait_for_dismiss=True: await kembalikan nilai dismiss (yes/no/all),
            # bukan None. Wajib dipanggil dari worker (kita di run_worker).
            return await self.app.push_screen(ConfirmDialog(tool_name, params),
                                              wait_for_dismiss=True)
        finally:
            bar.set_status("thinking")

    async def _ask_user(self, question: str) -> str:
        return await self.app.push_screen(AskDialog(question), wait_for_dismiss=True)
