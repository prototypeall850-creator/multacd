"""Textual App utama multacd. Config di-load di main.py (entry point)."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from textual.app import App
from textual.binding import Binding

from core.codebase import get_git_summary, project_label, scan_project
from core.config import Config, set_active_config
from core.llm_client import LLMClient
from core.mode_manager import ModeManager
from core.prompt_composer import PromptComposer, load_soul
from memory.context import ConversationContext
from tui import icons
from tui.screens.main_screen import MainScreen
from tui.themes import THEMES, resolve_theme_name

APP_VERSION = "0.0.0-beta"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class MultacdApp(App[None]):
    """App TUI. `config` wajib valid; `llm_client` opsional (buat test)."""

    BINDINGS = [
        # priority=True: menang atas binding widget fokus (mis. Ctrl+C = copy di Input).
        Binding("ctrl+c", "safe_quit", "Quit", priority=True),
        Binding("ctrl+q", "safe_quit", "Quit", priority=True),
    ]

    def __init__(self, config: Config, llm_client: LLMClient | None = None,
                 version: str = APP_VERSION) -> None:
        super().__init__()
        self.cfg = config
        # Fondasi DESIGN.md: theme + icon dipilih sekali saat startup.
        for _theme in THEMES:
            with suppress(ValueError):  # sudah terdaftar (re-init di test)
                self.register_theme(_theme)
        icons.setup(config.icon_style)
        self.llm_client = llm_client
        self.context = ConversationContext()
        # Pasang config sesi sebagai active config (Bug 3): tool research
        # (quick/deep_research, web_search, query_generator) membaca dari
        # sini — `--config PATH` dan `/model X` jadi dihormati. Referensi
        # objek yang sama dengan self.cfg, jadi mutasi /model ikut terlihat.
        set_active_config(self.cfg)
        self.version = version
        self.main_screen: MainScreen | None = None
        self._quit_armed = False
        # Mode + prompt composer (soul di-load sekali saat startup).
        soul = load_soul(project_dir=_PROJECT_ROOT)
        self.composer = PromptComposer(soul=soul)
        self.project_ctx = ""
        self.project_label = "?"
        self.workdir = Path.cwd()  # project yang dibuka sesi ini
        self.refresh_project_ctx()  # startup scan (fallback aman di dalam)
        # Auto git_status saat startup (silent, tanpa konfirmasi).
        self.git_summary: dict = get_git_summary(self.workdir)
        self.mode_manager = ModeManager(config, soul=soul,
                                        rescan_fn=self.refresh_project_ctx)
        self.mode_manager.set_git_enabled(bool(self.git_summary.get("is_repo")))
        self.composer.update_mode(self.mode_manager.get_mode_prompt())

    def refresh_project_ctx(self, root: Path | str | None = None) -> str:
        """Scan ulang codebase → update composer. Tidak pernah raise."""
        try:
            root_path = Path(root) if root else Path.cwd()
            self.project_ctx = scan_project(root_path)
            self.project_label = project_label(root_path)
        except Exception as e:
            self.project_ctx = f"(scan gagal: {type(e).__name__}: {e})"
            self.project_label = "?"
        self.composer.update_project_ctx(self.project_ctx)
        return f"🔍 {self.project_label} — context diperbarui."

    def on_mount(self) -> None:
        screen = MainScreen()
        self.main_screen = screen
        self.push_screen(screen)
        self.theme = resolve_theme_name(self.cfg.theme)

    def action_safe_quit(self) -> None:
        """Keluar graceful: kalau agent jalan, tekan 2x (kedua = paksa keluar)."""
        screen = self.main_screen
        busy = bool(screen is not None and screen._turn_running)
        if busy and not self._quit_armed:
            self._quit_armed = True
            self.notify("Agent masih jalan — tekan Ctrl+C lagi untuk paksa keluar.",
                        severity="warning", timeout=5)
            return
        self.exit()


if __name__ == "__main__":
    import sys

    from core.config import load_config

    try:
        cfg = load_config()
    except SystemExit:
        sys.exit(1)
    MultacdApp(cfg).run()
