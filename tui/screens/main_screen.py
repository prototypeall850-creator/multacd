"""Layar utama: status_bar + chat_panel + input_bar, tersambung ke agent_loop."""

from __future__ import annotations

import asyncio
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen

from core.agent_loop import (
    AgentDone,
    AgentError,
    AgentText,
    AgentToolDone,
    AgentToolStart,
    run_agent,
)
from core.codebase import get_git_summary
from tui.widgets.chat_panel import ChatPanel
from tui.widgets.confirm_dialog import AskDialog, ConfirmDialog
from tui.widgets.diff_viewer import DiffViewer
from tui.widgets.file_tree import FileOpenRequested, ProjectTree, modified_files
from tui.widgets.input_bar import InputBar, InputSubmitted
from tui.widgets.status_bar import StatusBar


class MainScreen(Screen):
    """Susun widget + handle event dari agent_loop."""

    BINDINGS = [
        ("ctrl+t", "toggle_tree", "File tree"),
        ("ctrl+g", "toggle_diff", "Diff"),
    ]

    CSS = """
    MainScreen {
        layout: vertical;
    }
    #status-bar {
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    #body {
        height: 1fr;
    }
    #file-tree {
        width: 36;
        display: none;
        border-right: solid $primary;
    }
    #chat-panel {
        height: 1fr;
        padding: 0 1;
    }
    #diff-viewer {
        display: none;
        height: auto;
        max-height: 40%;
        border-top: solid $warning;
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
        with Horizontal(id="body"):
            yield ProjectTree(self.app.workdir)
            yield ChatPanel()
        yield DiffViewer()
        yield InputBar()

    def on_mount(self) -> None:
        bar = self.query_one(StatusBar)
        bar.set_model(self.app.cfg.model)
        bar.set_mode(self.app.mode_manager.get_mode())
        bar.set_git(self.app.git_summary)
        bar.set_status("idle")
        self.query_one(InputBar).focus()
        self.run_worker(self._show_welcome())
        self.run_worker(self._git_watcher())

    async def _git_watcher(self) -> None:
        """Refresh segmen git status bar tiap 10 dtk (background, tanpa ganggu chat)."""
        while True:
            await asyncio.sleep(10)
            try:
                bar = self.query_one(StatusBar)
            except Exception:
                return  # screen sudah di-unmount
            try:
                summary = get_git_summary(self.app.workdir)
            except Exception:
                continue
            self.app.git_summary = summary
            bar.set_git(summary)

    async def _show_welcome(self) -> None:
        chat = self.query_one(ChatPanel)
        await chat.add_info(
            f"⚡ Selamat datang di multacd v{self.app.version} — model: {self.app.cfg.model}\n"
            f"📁 {self.app.project_label}\n"
            "Ketik pesan lalu Enter untuk kirim · Shift+Enter untuk newline · Ctrl+C keluar.\n"
            "Tool baca & git langsung jalan; tulis/shell/web minta izin [Y/N/A] dulu.\n"
            "Ketik /help buat daftar command · Ctrl+T file tree · Ctrl+G diff."
        )

    def _sync_mode_ui(self) -> None:
        """Samakan status bar + composer dengan mode/model aktif."""
        mm = self.app.mode_manager
        bar = self.query_one(StatusBar)
        bar.set_mode(mm.get_mode())
        bar.set_model(self.app.cfg.model)
        bar.set_git(self.app.git_summary)
        self.app.composer.update_mode(mm.get_mode_prompt())
        # Tandai ulang file modified kalau tree sedang tampil.
        tree = self.query_one(ProjectTree)
        if tree.display:
            tree.mark_modified(modified_files(self.app.workdir))

    async def on_input_submitted(self, event: InputSubmitted) -> None:
        self._submit(event.value)

    async def on_file_open_requested(self, event: FileOpenRequested) -> None:
        """Klik/Enter file di tree → agent baca file itu."""
        self._submit(f"Baca file {event.path} lalu jelaskan isinya secara ringkas.")

    def _submit(self, text: str) -> None:
        if self._turn_running:
            return  # abaikan submit ganda saat agent berpikir
        if not text.strip():
            return
        self._turn_running = True
        self.run_worker(self._run_turn(text))

    def action_toggle_tree(self) -> None:
        """Ctrl+T: tampil/sembunyi file tree (+ tandai file modified)."""
        tree = self.query_one(ProjectTree)
        if tree.display:
            tree.display = False
            self.query_one(InputBar).focus()
        else:
            tree.display = True
            tree.mark_modified(modified_files(self.app.workdir))
            tree.focus()

    def action_toggle_diff(self) -> None:
        """Ctrl+G: tampil/sembunyi git diff workdir.

        NOTE: bukan Ctrl+D — itu delete-char di Input (readline) dan
        dimakan widget sebelum sampai screen binding.
        """
        viewer = self.query_one(DiffViewer)
        if viewer.display:
            viewer.display = False
        else:
            viewer.refresh_diff(self.app.workdir)
            viewer.display = True

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
                active_tools=self.app.mode_manager.get_active_tools(),
                composer=self.app.composer,
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
