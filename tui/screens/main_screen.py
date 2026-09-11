"""Layar utama: status_bar + chat_panel + input_bar, tersambung ke agent_loop."""

from __future__ import annotations

import asyncio
from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import TextArea

from core.agent_loop import (
    AgentDone,
    AgentError,
    AgentText,
    AgentToolDone,
    AgentToolStart,
    AgentUsage,
    run_agent,
)
from core.codebase import get_git_summary
from core.research.bus import set_research_sink
from tui.widgets.chat_panel import ChatPanel
from tui.widgets.confirm_dialog import AskDialog
from tui.widgets.diff_viewer import DiffViewer
from tui.widgets.file_tree import FileOpenRequested, ProjectTree, modified_files
from tui.widgets.info_panel import InfoPanel, estimate_tokens
from tui.widgets.input_bar import InputBar, InputSubmitted
from tui.widgets.model_selector import ModelSelector
from tui.widgets.permission_popup import PermissionPopup
from tui.widgets.slash_palette import SlashPalette
from tui.widgets.sources_panel import (
    ExportResearchRequested,
    SourcePreviewRequested,
    SourcesPanel,
)
from tui.widgets.status_bar import StatusBar
from tui.widgets.thinking_bar import ThinkingBar


class MainScreen(Screen):
    """Susun widget + handle event dari agent_loop."""

    BINDINGS = [
        ("ctrl+t", "toggle_tree", "File tree"),
        ("ctrl+g", "toggle_diff", "Diff"),
        ("ctrl+r", "toggle_sources", "Sources"),
        ("ctrl+o", "open_models", "Models"),
        ("ctrl+i", "toggle_info", "Info"),
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
        width: 25%;
        min-width: 20;
        display: none;
        border-left: solid $primary;
    }
    #chat-panel {
        height: 1fr;
        padding: 0 1;
    }
    #thinking-bar {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    #sources-panel {
        width: 30%;
        min-width: 20;
        display: none;
        border-left: solid $primary;
        padding: 0 1;
    }
    #info-panel {
        width: 25%;
        min-width: 20;
        display: none;
        border-left: solid $accent;
        padding: 0 1;
    }
    #diff-viewer {
        display: none;
        height: auto;
        max-height: 40%;
        border-top: solid $warning;
        padding: 0 1;
    }
    #slash-palette {
        display: none;
        height: auto;
        max-height: 12;
        border: solid $primary;
        background: $surface;
        padding: 0 1;
    }
    #model-selector {
        display: none;
        height: auto;
        max-height: 16;
        border: solid $accent;
        background: $surface;
        padding: 0 1;
    }
    #permission-popup {
        display: none;
        height: auto;
        max-height: 7;
        border: solid $warning;
        background: $surface;
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
        self._tools_run = 0  # counter sesi buat info panel
        self._sess_prompt = 0  # token resmi provider (0 = belum ada laporan)
        self._sess_completion = 0

    def compose(self) -> ComposeResult:
        yield StatusBar()
        with Horizontal(id="body"):
            yield ChatPanel()
            yield ProjectTree(self.app.workdir)
            yield SourcesPanel()
            yield InfoPanel()
        yield DiffViewer()
        yield ThinkingBar()
        yield PermissionPopup()
        yield SlashPalette()
        yield ModelSelector()
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
        self.run_worker(self._maybe_update_notice())

    async def _git_watcher(self) -> None:
        """Refresh segmen git status bar (background, tanpa ganggu chat).

        Min-mode (Termux): 60 dtk sekali — hemat CPU/baterai di HP.
        """
        from tui.tokens import is_min_mode as _min
        while True:
            await asyncio.sleep(60 if _min() else 10)
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

    async def _maybe_update_notice(self) -> None:
        """Cek update di background; tampil sekali di chat kalau ada versi baru."""
        try:
            from core import updater
            res = await asyncio.to_thread(updater.check)
        except Exception:
            return  # silent — update check tidak boleh ganggu sesi
        if not res.get("update_available"):
            return
        try:
            chat = self.query_one(ChatPanel)
        except Exception:
            return
        await chat.add_info(
            f"⬆️ Update tersedia: multacd v{res['latest_version']} "
            f"(kamu: v{res['current_version']}) — jalankan: multacd update"
        )

    async def _show_welcome(self) -> None:
        chat = self.query_one(ChatPanel)
        await chat.show_splash(self.app.version, self.app.cfg.model,
                               self.app.mode_manager.get_mode())
        if getattr(self.app, "plugins", None):
            names = ", ".join(p.name for p in self.app.plugins)
            await chat.add_info(f"Plugin: {names}")
        await chat.add_info(
            f"{self.app.project_label} — Enter kirim · /help command · "
            "tulis/shell/web minta izin dulu."
        )

    def _sync_mode_ui(self) -> None:
        """Samakan status bar + composer dengan mode/model aktif."""
        mm = self.app.mode_manager
        bar = self.query_one(StatusBar)
        bar.set_mode(mm.get_mode())
        bar.set_model(self.app.cfg.model)
        bar.set_git(self.app.git_summary)
        self.app.composer.update_mode(mm.get_mode_prompt())
        # Keluar /research → sembunyikan panel sumber (lihat PLAN-phase3 §10).
        panel = self.query_one(SourcesPanel)
        if mm.get_mode() != "research":
            panel.display = False
        # Tandai ulang file modified kalau tree sedang tampil.
        tree = self.query_one(ProjectTree)
        if tree.display:
            tree.mark_modified(modified_files(self.app.workdir))
        self._refresh_info()

    def _refresh_info(self) -> None:
        """Update info panel (kalau tampil) — tak pernah raise."""
        try:
            info = self.query_one(InfoPanel)
        except Exception:
            return
        if not info.display:
            return
        try:
            chars = sum(len(str(m.get("content", "")))
                        for m in self.app.context.get_messages())
            real_total = self._sess_prompt + self._sess_completion
            # Token resmi kalau provider melapor; kalau tidak, heuristik ~.
            tokens_s = (f"{real_total:,}".replace(",", ".") if real_total
                        else f"~{estimate_tokens(chars):,}".replace(",", "."))
            git = self.app.git_summary
            git_s = "—"
            if git.get("is_repo"):
                git_s = str(git.get("branch", "?"))
                if git.get("modified"):
                    git_s += f" +{git['modified']}"
            data: dict = {
                "mode": self.app.mode_manager.get_mode(),
                "project": self.app.project_label,
                "git": git_s,
                "tokens": tokens_s,
                "messages": len(self.app.context),
                "tools": self._tools_run,
                "model": self.app.cfg.model,
            }
            if data["mode"] == "research":
                try:
                    src = self.query_one(SourcesPanel)
                    cur, tot = src._round
                    read = sum(1 for it in src._items
                               if it.get("status") in ("scraped", "snippet"))
                    data["round"] = f"{cur}/{tot}"
                    data["sources"] = f"{read} read"
                    data["topic"] = "aktif" if cur else "—"
                except Exception:
                    pass
            info.update_snapshot(data)
        except Exception:
            pass

    def action_toggle_info(self) -> None:
        """Ctrl+I: tampil/sembunyi info panel (DESIGN §11)."""
        info = self.query_one(InfoPanel)
        info.display = not info.display
        if info.display:
            self._refresh_info()
        else:
            self.query_one(InputBar).focus()

    async def on_input_submitted(self, event: InputSubmitted) -> None:
        sel = self.query_one(ModelSelector)
        if sel.is_open:
            self.model_select()
            return
        self.query_one(SlashPalette).close()
        self._submit(event.value)

    async def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Ketik / di awal input → buka palette, filter real-time."""
        if event.text_area.id != "input-bar":
            return
        text = event.text_area.text
        sel = self.query_one(ModelSelector)
        if sel.is_open:
            # Mode selector: teks polos = query filter (bukan command).
            if not text.startswith("/"):
                sel.refilter(text)
                return
            sel.close()  # user ketik / → keluar mode selector
        pal = self.query_one(SlashPalette)
        if pal.suppress_next:
            pal.suppress_next = False
            pal.close()
            return
        if text.startswith("/") and " " not in text and "\n" not in text:
            pal.open(text[1:])
        else:
            pal.close()

    def palette_select(self) -> None:
        """Enter/klik di palette: submit (atau autocomplete kalau butuh arg)."""
        pal = self.query_one(SlashPalette)
        inbar = self.query_one(InputBar)
        cmd = pal.selected_command
        if cmd is None:
            pal.close()
            return
        if SlashPalette.needs_arg(cmd):
            inbar.text = cmd + " "
            pal.close()
            inbar.focus()
        else:
            inbar.clear()
            pal.close()
            self.post_message(InputSubmitted(cmd))

    def palette_autocomplete(self) -> None:
        """Tab: tulis command terpilih ke input tanpa submit."""
        pal = self.query_one(SlashPalette)
        inbar = self.query_one(InputBar)
        cmd = pal.selected_command
        pal.suppress_next = True  # Changed dari set text tidak buka lagi
        if cmd is not None:
            inbar.text = cmd
        pal.close()
        inbar.focus()

    async def on_file_open_requested(self, event: FileOpenRequested) -> None:
        """Klik/Enter file di tree → agent baca file itu."""
        self._submit(f"Baca file {event.path} lalu jelaskan isinya secara ringkas.")

    async def on_key(self, event: events.Key) -> None:
        """Fallback permission: kalau bar menunggu dan tombol jawab ditekan
        di widget lain (tree/panel), teruskan. InputBar sudah handle duluan
        untuk kasusnya sendiri (TextArea menelan keystrokes)."""
        if event.key.lower() not in ("y", "n", "a", "enter", "escape"):
            return
        try:
            perm = self.query_one(PermissionPopup)
        except Exception:
            return
        if perm.is_waiting and perm.answer_key(event.key):
            event.prevent_default()
            event.stop()

    def _submit(self, text: str) -> None:
        if self._turn_running:
            return  # abaikan submit ganda saat agent berpikir
        if not text.strip():
            return
        # /model tanpa argumen → buka selector popup (DESIGN §12 v2),
        # bukan sekadar print model aktif.
        if text.strip().lower() == "/model":
            self.model_open()
            return
        self._turn_running = True
        self.run_worker(self._run_turn(text))

    def action_open_models(self) -> None:
        """Ctrl+O: buka model selector (DESIGN §12)."""
        self.model_open()

    def model_open(self) -> None:
        """Buka selector; tutup palette kalau sedang terbuka."""
        self.query_one(SlashPalette).close()
        self.query_one(ModelSelector).open(self.app.cfg.model)
        self.query_one(InputBar).focus()

    def model_select(self) -> None:
        """Enter di selector: submit '/model <nama>' kayak ketik manual."""
        sel = self.query_one(ModelSelector)
        inbar = self.query_one(InputBar)
        name = sel.selected
        if name:
            sel.mark_used(name)
        sel.close()
        inbar.clear()
        inbar.focus()
        if name:
            self._submit(f"/model {name}")

    def model_favorite(self) -> None:
        """Ctrl+F di selector: tandai favorit."""
        self.query_one(ModelSelector).toggle_favorite()

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

    def action_toggle_sources(self) -> None:
        """Ctrl+R: tampil/sembunyi Sources Panel (mode /research)."""
        panel = self.query_one(SourcesPanel)
        if panel.display:
            panel.display = False
            self.query_one(InputBar).focus()
        else:
            panel.display = True

    async def on_source_preview_requested(
        self, event: SourcePreviewRequested
    ) -> None:
        """Klik sumber di panel → tampilkan preview di chat."""
        chat = self.query_one(ChatPanel)
        preview = self.query_one(SourcesPanel).get_preview(event.url)
        await chat.add_info(preview)

    async def on_export_research_requested(
        self, event: ExportResearchRequested
    ) -> None:
        """Tombol Export → minta agent simpan hasil research terakhir."""
        _ = event
        self._submit("Export hasil research di atas ke file .md.")

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
        think = self.query_one(ThinkingBar)
        try:
            inbar.set_busy(True)
            bar.set_status("thinking")
            think.show("thinking")
            # /clear: bersihkan UI dulu biar command + respons tetap kelihatan.
            # (Single source of truth parsing tetap ModeManager di agent_loop.)
            stripped = text.strip().lower()
            if stripped == "/clear" or stripped.startswith("/clear "):
                await chat.clear()
            await chat.add_user(text)
            await chat.start_assistant()
            # Pasang sink research: event orchestrator (quick/deep) diteruskan
            # ke panel via call_from_thread (aman dari thread manapun).
            set_research_sink(
                lambda ev: self.app.call_from_thread(
                    self._apply_research_event, ev))
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
                    think.show(event.name)
                    await chat.add_tool_row(event.call_id, event.name, event.params)
                elif isinstance(event, AgentToolDone):
                    think.show("thinking")
                    self._tools_run += 1
                    await chat.update_tool_row(event.call_id, event.name,
                                               event.success, event.result)
                elif isinstance(event, AgentDone):
                    pass  # teks sudah ter-stream penuh
                elif isinstance(event, AgentUsage):
                    self._sess_prompt += event.prompt_tokens
                    self._sess_completion += event.completion_tokens
                elif isinstance(event, AgentError):
                    await chat.add_error(event.message)
        finally:
            set_research_sink(None)
            think.hide()
            self._sync_mode_ui()
            bar.set_status("idle")
            inbar.set_busy(False)
            inbar.focus()
            self._turn_running = False

    def _apply_research_event(self, ev: dict[str, Any]) -> None:
        """Terapkan satu event orchestrator ke SourcesPanel (jalan di app loop)."""
        try:
            panel = self.query_one(SourcesPanel)
        except Exception:
            return
        kind = ev.get("type", "")
        try:
            if kind == "queries":
                panel.add_queries(len(ev.get("queries", [])))
            elif kind == "sources":
                panel.update_sources(ev.get("sources", []))
                if (self.app.mode_manager.get_mode() == "research"
                        and not panel.display):
                    panel.display = True  # auto-tampil saat hasil masuk
            elif kind == "source":
                panel.update_source(ev.get("url", ""), ev.get("status", "?"),
                                    ev.get("preview", ""))
            elif kind in ("round_start", "round"):
                panel.set_round(ev.get("round", 0), ev.get("total", 0))
            elif kind == "limit":
                panel.set_notice(ev.get("reason", ""))
            elif kind == "synthesizing":
                panel.set_notice("menyusun jawaban...")
            elif kind in ("answer", "report"):
                panel.set_notice("")
                panel.set_export_visible(True)
        except Exception:
            pass

    async def _confirm(self, tool_name: str, params: dict[str, Any]) -> str:
        bar = self.query_one(StatusBar)
        think = self.query_one(ThinkingBar)
        perm = self.query_one(PermissionPopup)
        bar.set_status("waiting")
        think.hide()  # permission bar gantikan thinking bar sementara
        try:
            return await perm.ask(tool_name, params)
        finally:
            bar.set_status("thinking")
            think.show("thinking")

    async def _ask_user(self, question: str) -> str:
        return await self.app.push_screen(AskDialog(question), wait_for_dismiss=True)
