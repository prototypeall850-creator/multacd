"""Layar utama: status_bar + chat_panel + input_bar, tersambung ke agent_loop."""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from typing import Any

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Static, TextArea

from core.agent_events import (
    AgentContinue,
    AgentError,
    AgentEvent,
    AgentText,
    AgentToolDone,
    AgentToolStart,
)
from core.codebase import get_git_summary
from core.session_state import AgentStatus, SessionState
from tui.controllers.agent_controller import AgentController, TurnHooks
from tui.widgets.chat_panel import ChatPanel, render_meta
from tui.widgets.confirm_dialog import AskDialog, ContinueDialog
from tui.widgets.context_sidebar import ContextSidebar
from tui.widgets.diff_viewer import DiffViewer
from tui.widgets.file_tree import FileOpenRequested, ProjectTree, modified_files
from tui.widgets.footer_bar import FooterBar, short_workdir
from tui.widgets.info_panel import InfoPanel, estimate_tokens
from tui.widgets.input_bar import InputBar, InputSubmitted
from tui.widgets.model_selector import ModelSelector
from tui.widgets.permission_popup import PermissionPopup
from tui.widgets.provider_selector import ProviderSelector
from tui.widgets.session_bar import SessionBar
from tui.widgets.slash_palette import SlashPalette
from tui.widgets.sources_panel import (
    ExportResearchRequested,
    SourcePreviewRequested,
    SourcesPanel,
)
from tui.widgets.status_bar import StatusBar, agent_status_for
from tui.widgets.thinking_bar import ThinkingBar


class MainScreen(Screen):
    """Susun widget + handle event dari agent_loop."""

    BINDINGS = [
        ("ctrl+t", "toggle_tree", "File tree"),
        ("ctrl+g", "toggle_diff", "Diff"),
        ("ctrl+r", "toggle_sources", "Sources"),
        ("ctrl+o", "open_models", "Models"),
        ("ctrl+i", "toggle_info", "Info"),
        ("ctrl+y", "copy_last", "Copy"),
        ("ctrl+p", "open_palette", "Commands"),
    ]

    CSS = """
    MainScreen {
        layout: vertical;
    }
    #session-bar {
        height: 1;
        background: $surface;
        padding: 0 1;
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
        height: auto;
        padding: 0;
    }
    #context-sidebar {
        width: 24%;
        min-width: 22;
        border-left: solid $primary;
        padding: 0 1;
    }
    #mcp-body {
        height: auto;
        color: $text-muted;
        padding-top: 1;
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
    #slash-palette.overlay {
        position: absolute;
        /* offset-% resolve ke ukuran sendiri: 33% x 60% = 20% layar,
           center horizontal di semua lebar. y scalar: di bawah bar atas. */
        offset: 33% 4;
        width: 60%;
        max-height: 60%;
    }
    #slash-palette .slash-group {
        color: $text-muted;
        text-style: bold;
    }
    #model-selector {
        display: none;
        position: absolute;
        offset: 33% 4;
        width: 60%;
        height: auto;
        max-height: 60%;
        border: solid $accent;
        background: $surface;
        padding: 0 1;
    }
    #provider-selector {
        display: none;
        position: absolute;
        offset: 33% 4;
        width: 60%;
        height: auto;
        max-height: 60%;
        border: solid $primary;
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
    #input-meta {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    #footer-bar {
        height: 1;
        background: $surface;
        padding: 0 1;
        color: $text-muted;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        # Satu sumber kebenaran status agent (R3). Dulu 5 field tersebar
        # (_turn_running/_tools_run/_sess_*) — sekarang SessionState.
        self.session = SessionState()
        # Controller loop agent (R4) — dibuat sekali biar approve [A]
        # persist lintas turn (issue #32).
        self._agent_ctl: AgentController | None = None
        # TUI-R1 shell: override manual sidebar (None = ikut lebar terminal),
        # keputusan layout terakhir (biar apply idempotent), lebar terakhir.
        self._sidebar_manual: bool | None = None
        self._last_layout: object | None = None
        self._last_width: int = 0

    @property
    def _turn_running(self) -> bool:
        """Kompat: tui/app.py quit-guard baca atribut ini."""
        return self.session.busy

    @_turn_running.setter
    def _turn_running(self, value: bool) -> None:
        if value:
            self.session.begin_turn()
        else:
            self.session.end_turn()

    def compose(self) -> ComposeResult:
        yield SessionBar()
        yield StatusBar()
        with Horizontal(id="body"):
            yield ChatPanel()
            yield ProjectTree(self.app.workdir)
            yield SourcesPanel()
            yield ContextSidebar()
        yield DiffViewer()
        yield ThinkingBar()
        yield PermissionPopup()
        yield SlashPalette()
        yield ModelSelector()
        yield ProviderSelector()
        yield Static("", id="input-meta")
        yield InputBar()
        yield FooterBar()

    def on_mount(self) -> None:
        bar = self.query_one(StatusBar)
        bar.set_model(self.app.cfg.model)
        bar.set_mode(self.app.mode_manager.get_mode())
        bar.set_git(self.app.git_summary)
        bar.render_state(self.session)  # IDLE awal — dari state, konsisten R5
        self._refresh_shell()
        self._apply_layout(self._layout_width())
        self._refresh_info()  # sidebar langsung terisi, bukan "(info)"
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
            f"Update tersedia: multacd v{res['latest_version']} "
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
            self._refresh_tree_marks(tree)
        self._refresh_shell()
        self._apply_layout(self._layout_width())
        self._refresh_info()

    def _refresh_tree_marks(self, tree: ProjectTree | None = None) -> None:
        """Reload tree dari disk + tandai modified (file baru agent muncul).

        reload() async di dalam — mark ditunda 0.5 dtk biar node kebentuk.
        Tak pernah raise; diam kalau tree disembunyikan user di tengah jalan.
        """
        try:
            tree = tree or self.query_one(ProjectTree)
        except Exception:
            return
        if not tree.display:
            return
        with suppress(Exception):
            tree.reload()
        with suppress(Exception):
            self.set_timer(0.5, self._mark_tree_delayed)

    def _mark_tree_delayed(self) -> None:
        try:
            tree = self.query_one(ProjectTree)
        except Exception:
            return
        if not tree.display:
            return
        with suppress(Exception):
            tree.mark_modified(modified_files(self.app.workdir))

    def _usage_strings(self) -> tuple[str, str]:
        """(tokens_s, cost_s) dari SessionState/context. Tak pernah raise.

        Token resmi kalau provider melapor; kalau tidak, heuristik ~.
        Cost: angka resmi kalau >0, else — (lokal). Dipakai panel + footer.
        """
        try:
            chars = sum(len(str(m.get("content", "")))
                        for m in self.app.context.get_messages())
        except Exception:
            chars = 0
        real_total = self.session.prompt_tokens + self.session.completion_tokens
        tokens_s = (f"{real_total:,}".replace(",", ".") if real_total
                    else f"~{estimate_tokens(chars):,}".replace(",", "."))
        cost_s = (f"${self.session.cost_usd:.3f} est" if self.session.cost_usd > 0
                  else "—")
        return tokens_s, cost_s

    def _refresh_shell(self) -> None:
        """Sync session bar + input meta + footer + MCP (TUI-R1).

        Read-only dari state existing. Tak pernah raise.
        """
        with suppress(Exception):
            self.query_one(SessionBar).set_title(self.app.project_label or "—")
        with suppress(Exception):
            mode = self.app.mode_manager.get_mode()
            short = (self.app.cfg.model or "?").split("/")[-1][:28]
            self.query_one("#input-meta", Static).update(
                Text(f"{mode} · {short}", style="dim"))
        with suppress(Exception):
            tokens_s, cost_s = self._usage_strings()
            work = short_workdir(str(self.app.workdir))
            self.query_one(FooterBar).set_data(work, f"{tokens_s} · {cost_s}")
        with suppress(Exception):
            self.query_one(ContextSidebar).set_mcp()

    def _layout_width(self) -> int:
        """Lebar terminal saat ini; fallback aman buat test/worker."""
        try:
            w = self.size.width
            if w:
                return int(w)
        except Exception:
            pass
        from tui.tokens import term_width
        return term_width()

    def on_resize(self, event: events.Resize) -> None:
        """Terminal di-resize → terapkan breakpoint sidebar/footer (TUI-R1)."""
        with suppress(Exception):
            self._apply_layout(event.size.width)

    def _apply_layout(self, width: int) -> None:
        """Terapkan ShellLayout; sentuh Textual hanya bila keputusan berubah."""
        from tui.layout import layout_for_width
        self._last_width = width
        lay = layout_for_width(width, self._sidebar_manual)
        if lay != self._last_layout:
            self._last_layout = lay
            with suppress(Exception):
                sidebar = self.query_one(ContextSidebar)
                sidebar.display = lay.sidebar_visible
                sidebar.styles.width = lay.sidebar_width
        with suppress(Exception):
            self.query_one(FooterBar).set_compact(lay.footer_compact)

    def _refresh_info(self) -> None:
        """Update info panel (kalau sidebar tampil) — tak pernah raise."""
        try:
            info = self.query_one(InfoPanel)
        except Exception:
            return
        try:
            if not self.query_one(ContextSidebar).display:
                return
        except Exception:
            return
        try:
            tokens_s, cost_s = self._usage_strings()
            # Split in/out resmi kalau provider melapor; kalau tidak → —
            # (estimasi heuristik cuma tahu total, jangan sok split).
            real = self.session.prompt_tokens + self.session.completion_tokens
            if real:
                prompt_s = f"{self.session.prompt_tokens:,}".replace(",", ".")
                comp_s = f"{self.session.completion_tokens:,}".replace(",", ".")
            else:
                prompt_s = comp_s = "—"
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
                "prompt": prompt_s,
                "completion": comp_s,
                "cost": cost_s,
                "messages": len(self.app.context),
                "tools": self.session.tool_count,
                "model": self.app.cfg.model,
                "status": agent_status_for(self.session.status),
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
        """Ctrl+I: override manual sidebar (auto = ikut lebar terminal)."""
        try:
            visible = self.query_one(ContextSidebar).display
        except Exception:
            return
        self._sidebar_manual = not visible
        self._apply_layout(self._last_width)
        if self._sidebar_manual:
            self._refresh_info()
        else:
            with suppress(Exception):
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
        if pal.overlay_open:
            # Mode Ctrl+P: input = search field (teks apa pun = filter).
            needle = text[1:] if text.startswith("/") else text
            pal.refilter(needle.split(" ")[0].split("\n")[0])
            return
        prov = self.query_one(ProviderSelector)
        if prov.is_open:
            prov.close()  # ketikan manual = batal pilih provider
            return
        if pal.suppress_next:
            pal.suppress_next = False
            pal.close()
            return
        if text.startswith("/") and " " not in text and "\n" not in text:
            pal.open(text[1:])
        else:
            pal.close()

    def action_open_palette(self) -> None:
        """Ctrl+P: command palette overlay (reuse SlashPalette, TUI-R3)."""
        pal = self.query_one(SlashPalette)
        inbar = self.query_one(InputBar)
        if pal.overlay_open:
            pal.close()
            inbar.focus()
            return
        pal.close()  # reset mode inline kalau sedang terbuka
        pal.open("", overlay=True)
        inbar.focus()

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
        if event.key.lower() not in ("y", "n", "a", "e", "b", "enter", "escape"):
            return
        try:
            perm = self.query_one(PermissionPopup)
        except Exception:
            return
        if perm.is_waiting and perm.answer_key(event.key):
            event.prevent_default()
            event.stop()

    def _submit(self, text: str) -> None:
        if self.session.busy:
            return  # abaikan submit ganda saat agent berpikir
        if not text.strip():
            return
        # /model tanpa argumen → buka selector popup (DESIGN §12 v2),
        # bukan sekadar print model aktif.
        if text.strip().lower() == "/model":
            self.model_open()
            return
        # /copy [n] → salin jawaban assistant (TUI-local, tak ke LLM).
        parts = text.strip().split()
        if parts and parts[0].lower() == "/copy":
            n = 1
            if len(parts) > 1:
                try:
                    n = max(1, int(parts[1]))
                except ValueError:
                    n = 1
            self.copy_assistant(n)
            return
        # /connect [provider] → selector popup (tanpa arg) atau langsung
        # pasang key (dengan arg). TUI-local, tanpa LLM.
        if parts and parts[0].lower() == "/connect":
            if len(parts) < 2 or not parts[1].strip():
                self.provider_open()
                return
            self.session.begin_turn()
            self.run_worker(self._connect_flow(parts[1]))
            return
        # /models [provider] → selector model provider itu (TUI-local).
        if parts and parts[0].lower() == "/models":
            arg = parts[1] if len(parts) > 1 else ""
            if arg:
                from tui.widgets.model_selector import for_provider
                if for_provider(arg, self.app.cfg.model) is None:
                    self.session.begin_turn()
                    self.run_worker(self._connect_note(
                        f"Provider `{arg}` tak dikenal. /connect tanpa arg "
                        "buat daftar."))
                    return
            self.model_open(provider=arg or None)
            return
        self._turn_running = True
        self.run_worker(self._run_turn(text))

    def action_copy_last(self) -> None:
        """Ctrl+Y: salin jawaban terakhir."""
        self.copy_assistant(1)

    def copy_assistant(self, n: int = 1) -> None:
        """Salin jawaban assistant ke-n ke clipboard + lapor di chat."""
        try:
            chat = self.query_one(ChatPanel)
            text = chat.assistant_history(n)
        except Exception:
            return
        if not text:
            self.run_worker(self._copy_note("(belum ada jawaban buat disalin)"))
            return
        self.run_worker(self._copy_do(text))

    async def _copy_do(self, text: str) -> None:
        from core.clipboard import copy_text
        try:
            msg = await asyncio.to_thread(copy_text, text)
        except Exception as e:
            msg = f"gagal salin ({e})."
        with suppress(Exception):
            await self.query_one(ChatPanel).add_info(msg)

    async def _copy_note(self, msg: str) -> None:
        with suppress(Exception):
            await self.query_one(ChatPanel).add_info(msg)

    def action_open_models(self) -> None:
        """Ctrl+O: buka model selector (DESIGN §12)."""
        self.model_open()

    def model_open(self, provider: str | None = None) -> None:
        """Buka selector; tutup palette/provider kalau sedang terbuka."""
        self.query_one(SlashPalette).close()
        self.query_one(ProviderSelector).close()
        self.query_one(ModelSelector).open(self.app.cfg.model,
                                           provider=provider)
        self.query_one(InputBar).focus()

    def model_select(self) -> None:
        """Enter di selector: submit '/model <nama>' kayak ketik manual."""
        sel = self.query_one(ModelSelector)
        inbar = self.query_one(InputBar)
        name = sel.selected
        if name:
            sel.mark_used(name)
        full = sel.selected_qualified
        sel.close()
        inbar.clear()
        inbar.focus()
        if full:
            self._submit(f"/model {full}")

    def provider_open(self) -> None:
        """Buka selector provider (TUI-R4 §14); tutup popup lain."""
        from core.providers import provider_id_of
        from tui.screens.setup_wizard import PROVIDERS, SEARCH_OPTIONS
        self.query_one(SlashPalette).close()
        self.query_one(ModelSelector).close()
        cfg = self.app.cfg
        cur = provider_id_of(cfg.model)
        llm = [(p.id, p.label,
                (p.id in cfg.provider_keys
                 or (p.id == cur and bool(cfg.api_key))))
               for p in PROVIDERS]
        search = [(sid, desc, cfg.search_provider == sid)
                  for sid, desc in SEARCH_OPTIONS if sid != "skip"]
        self.query_one(ProviderSelector).open(llm, search)
        self.query_one(InputBar).focus()

    def provider_select(self) -> None:
        """Enter di selector: submit '/connect <id>' kayak ketik manual."""
        sel = self.query_one(ProviderSelector)
        picked = sel.selected
        sel.close()
        inbar = self.query_one(InputBar)
        inbar.focus()
        if picked is not None:
            self._submit(f"/connect {picked[1]}")

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
            self._refresh_tree_marks(tree)
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

    def _live_sink(self, call_id: str, line: str) -> None:
        """Terima baris live dari thread worker tool → antre ke app loop."""
        with suppress(Exception):
            self.app.call_from_thread(self._queue_live, call_id, line)

    def _queue_live(self, call_id: str, line: str) -> None:
        """Jalan di app loop: mount/update widget live (thread-safe di sini)."""
        try:
            chat = self.query_one(ChatPanel)
        except Exception:
            return
        self.run_worker(chat.add_live_output(call_id, line))

    async def _connect_note(self, text: str) -> None:
        """Info TUI-local + reset flag submit (dipakai /models tak dikenal)."""
        try:
            await self.query_one(ChatPanel).add_info(text)
        finally:
            with suppress(Exception):
                self.query_one(InputBar).focus()
            self.session.end_turn()

    async def _connect_flow(self, arg: str) -> None:
        """Sambung provider via dialog (TUI-local, tanpa LLM).

        `/connect` = daftar + status; `/connect <id>` = pasang key
        (+ base bila perlu) lalu simpan. LLM dan search satu pintu.
        """
        from core.config import save_config_updates
        from tui.screens.setup_wizard import PROVIDERS, SEARCH_OPTIONS
        from tui.widgets.confirm_dialog import AskDialog
        chat = self.query_one(ChatPanel)
        inbar = self.query_one(InputBar)
        cfg = self.app.cfg
        try:
            await chat.add_user(f"/connect {arg}".strip())
            llm_ids = [p.id for p in PROVIDERS]
            search_ids = [sid for sid, _ in SEARCH_OPTIONS
                          if sid != "skip"]
            pid = arg.strip().lower()
            if pid in llm_ids:
                label = next(p.label for p in PROVIDERS if p.id == pid)
                key = await self.app.push_screen(
                    AskDialog(f"API key {label} (Esc = batal):",
                              password=True),
                    wait_for_dismiss=True)
                if not key or key == "(dibatalkan)":
                    await chat.add_info("Dibatalkan — key tidak diubah.")
                    return
                updates: dict[str, Any] = {"provider_keys": {pid: key}}
                cfg.provider_keys[pid] = key
                if pid in ("custom", "ollama"):
                    default = next(p.default_base for p in PROVIDERS
                                   if p.id == pid)
                    cur_base = cfg.provider_bases.get(pid, "")
                    base = await self.app.push_screen(
                        AskDialog(
                            f"Endpoint {label} (kosongkan = bawaan"
                            + (f" {cur_base or default}" if (cur_base or default) else "")
                            + ", - = hapus):",
                            initial=cur_base or default),
                        wait_for_dismiss=True)
                    if base is None or base == "(dibatalkan)":
                        await chat.add_info("Dibatalkan — base tidak diubah.")
                        return
                    base = base.strip()
                    if base == "-":
                        cfg.provider_bases.pop(pid, None)
                        updates["provider_bases"] = {pid: ""}
                    elif base:
                        cfg.provider_bases[pid] = base.rstrip("/")
                        updates["provider_bases"] = {
                            pid: base.rstrip("/")}
                try:
                    save_config_updates(updates)
                    saved = " (tersimpan)"
                except OSError as e:
                    saved = f" (gagal simpan: {e} — sesi ini saja)"
                await chat.add_info(
                    f"`{pid}` connected{saved}. Ganti model: /models {pid}")
                return
            if pid in search_ids:
                if pid == "duckduckgo":
                    cfg.search_provider = "duckduckgo"
                    try:
                        save_config_updates({"search_provider": "duckduckgo"})
                        saved = " (tersimpan)"
                    except OSError as e:
                        saved = f" (gagal simpan: {e})"
                    await chat.add_info(
                        f"Search → duckduckgo (gratis){saved}.")
                    return
                key = await self.app.push_screen(
                    AskDialog(f"Search key {pid} (Esc = batal):",
                              password=True),
                    wait_for_dismiss=True)
                if not key or key == "(dibatalkan)":
                    await chat.add_info("Dibatalkan — key tidak diubah.")
                    return
                cfg.search_provider = pid
                cfg.search_api_key = key
                try:
                    save_config_updates({"search_provider": pid,
                                         "search_api_key": key})
                    saved = " (tersimpan)"
                except OSError as e:
                    saved = f" (gagal simpan: {e} — sesi ini saja)"
                await chat.add_info(
                    f"Search → {pid}{saved}. Coba: /research lalu tanya.")
                return
            await chat.add_info(
                f"Provider `{pid}` tak dikenal. /connect tanpa arg buat daftar.")
        finally:
            self._sync_mode_ui()
            with suppress(Exception):
                inbar.focus()
            self.session.end_turn()

    def _agent(self) -> AgentController:
        """Controller sesi (dibuat sekali — checker [A] persist lintas turn)."""
        if self._agent_ctl is None:
            self._agent_ctl = AgentController(
                self.session, self.app.cfg, self.app.context)
        ctl = self._agent_ctl
        # Live refs — hormati /model & /mode terbaru tiap turn.
        ctl.llm_client = self.app.llm_client
        ctl.composer = self.app.composer
        ctl.mode_manager = self.app.mode_manager
        return ctl

    async def _run_turn(self, text: str) -> None:
        chat = self.query_one(ChatPanel)
        bar = self.query_one(StatusBar)
        inbar = self.query_one(InputBar)
        think = self.query_one(ThinkingBar)
        # TUI-R2 §7: durasi + token turn ini buat meta jawaban (ukur di UI,
        # read-only dari SessionState — agent runtime tak disentuh).
        t0 = time.monotonic()
        tok0 = self.session.completion_tokens
        try:
            inbar.set_busy(True)
            bar.render_state(self.session)
            think.render_state(self.session)
            # §10: turn pertama = splash bubar, masuk layout normal.
            await chat.dismiss_splash()
            # /clear: bersihkan UI dulu biar command + respons tetap kelihatan.
            # (Single source of truth parsing tetap ModeManager di agent_loop.)
            stripped = text.strip().lower()
            if stripped == "/clear" or stripped.startswith("/clear "):
                await chat.clear()
            await chat.add_user(text)
            await chat.start_assistant()

            async def _emit(event: AgentEvent) -> None:
                if isinstance(event, AgentText):
                    await chat.append_assistant_text(event.delta)
                elif isinstance(event, AgentToolStart):
                    think.render_state(self.session)
                    await chat.add_tool_row(event.call_id, event.name,
                                            event.params)
                elif isinstance(event, AgentToolDone):
                    think.render_state(self.session)
                    await chat.drop_live_output(event.call_id)
                    await chat.update_tool_row(event.call_id, event.name,
                                               event.success, event.result)
                elif isinstance(event, AgentError):
                    await chat.add_error(event.message)
                # AgentDone: teks sudah ter-stream; AgentUsage/Continue:
                # sudah dilipat ke session oleh controller.

            async def _continue_prompt(ev: AgentContinue) -> bool:
                choice = await self.app.push_screen(
                    ContinueDialog(ev.summary, ev.limit),
                    wait_for_dismiss=True)
                if choice == "lanjut":
                    await chat.add_info(
                        f"Lanjut setelah {ev.tool_count} tool call…")
                    return True
                await chat.add_info(
                    "Berhenti di batas iterasi — ketik pesan buat lanjut manual.")
                return False

            hooks = TurnHooks(
                emit=_emit,
                continue_prompt=_continue_prompt,
                confirm=self._confirm,
                ask_user=self._ask_user,
                live=self._live_sink,
                research=lambda ev: self.app.call_from_thread(
                    self._apply_research_event, ev),
            )
            await self._agent().run_turn(
                text, hooks,
                active_tools=self.app.mode_manager.get_active_tools(),
            )
        finally:
            dur = time.monotonic() - t0
            dtok = self.session.completion_tokens - tok0
            with suppress(Exception):
                meta = render_meta(self.app.mode_manager.get_mode(),
                                   self.app.cfg.model, dur, dtok)
                await chat.close_assistant(meta)
            self.session.end_turn()
            think.render_state(self.session)
            bar.render_state(self.session)
            self._sync_mode_ui()
            inbar.set_busy(False)
            inbar.focus()

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
        self.session.status = AgentStatus.WAITING_PERMISSION
        bar.render_state(self.session)
        think.render_state(self.session)
        try:
            # #4: preview diff otomatis sebelum approve commit.
            if tool_name == "git_commit":
                await self.query_one(ChatPanel).add_diff_preview(
                    str(params.get("workdir", ".")))
            ans = await perm.ask(tool_name, params)
            # #4: Edit → dialog pesan baru (prefill). Batal = tolak.
            if ans == "edit:":
                cur = str(params.get("message", ""))
                new_msg = await self.app.push_screen(
                    AskDialog("Edit pesan commit:", initial=cur),
                    wait_for_dismiss=True)
                if not new_msg or new_msg == "(dibatalkan)":
                    return "no"
                return f"edit:{new_msg}"
            return ans
        finally:
            # Balik THINKING (bukan EXECUTING): visual sama kayak dulu
            # ("thinking", bukan "running X") sampai event berikutnya.
            self.session.status = AgentStatus.THINKING
            bar.render_state(self.session)
            think.render_state(self.session)

    async def _ask_user(self, question: str) -> str:
        return await self.app.push_screen(AskDialog(question), wait_for_dismiss=True)
