"""Textual App utama multacd. Config di-load di main.py (entry point)."""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from core.config import Config
from core.llm_client import LLMClient
from core.mode_manager import ModeManager
from core.prompt_composer import PromptComposer, load_soul
from memory.context import ConversationContext
from tui.screens.main_screen import MainScreen

APP_VERSION = "0.0.0-beta"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class MultacdApp(App[None]):
    """App TUI. `config` wajib valid; `llm_client` opsional (buat test)."""

    BINDINGS = [
        ("ctrl+c", "safe_quit", "Quit"),
        ("ctrl+q", "safe_quit", "Quit"),
    ]

    def __init__(self, config: Config, llm_client: LLMClient | None = None,
                 version: str = APP_VERSION) -> None:
        super().__init__()
        self.cfg = config
        self.llm_client = llm_client
        self.context = ConversationContext()
        self.version = version
        self.main_screen: MainScreen | None = None
        self._quit_armed = False
        # Mode + prompt composer (soul di-load sekali saat startup).
        soul = load_soul(project_dir=_PROJECT_ROOT)
        self.mode_manager = ModeManager(config, soul=soul)
        self.composer = PromptComposer(soul=soul)
        self.composer.update_mode(self.mode_manager.get_mode_prompt())

    def on_mount(self) -> None:
        screen = MainScreen()
        self.main_screen = screen
        self.push_screen(screen)
        self.theme = "textual-dark" if self.cfg.theme == "dark" else "textual-light"

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
