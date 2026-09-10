"""Mode manager — mode agent + parse slash command.

Mode aktif:
    code      → Coding Agent (default, penuh di Phase 2)
    research  → placeholder, aktif Phase 3
    personal  → placeholder, aktif Phase 4

Command yang dikenal (lihat HELP_TEXT):
    /code /research /personal /clear /scan /model [nama] /help /soul

Command di-intercept sebelum LLM (lihat core/agent_loop.py):
tidak masuk history, tidak panggil LLM.

Test cepat:
    python -m core.mode_manager
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import Config

MODE_CODE = "code"
MODE_RESEARCH = "research"
MODE_PERSONAL = "personal"

HELP_TEXT = (
    "📖 Command multacd:\n"
    "  /code          → mode Coding Agent (default)\n"
    "  /research      → Research Agent (coming Phase 3)\n"
    "  /personal      → Personal Agent (coming Phase 4)\n"
    "  /clear         → bersihkan history, mulai sesi baru\n"
    "  /scan          → scan ulang codebase project\n"
    "  /model [nama]  → lihat / ganti model (cth: /model openai/gpt-4o)\n"
    "  /soul          → tampilkan kepribadian agent yang aktif\n"
    "  /help          → tampilkan pesan ini"
)

MODE_PROMPTS = {
    MODE_CODE: (
        "Kamu sedang dalam Coding Agent mode. "
        "Kamu punya akses ke: filesystem, shell, git, "
        "run_python, lint_python, run_tests. "
        "Fokus membantu user dengan kode dan development workflow."
    ),
    MODE_RESEARCH: (
        "Kamu sedang dalam Research Agent mode. "
        "(Placeholder Phase 3 — instruksi penuh menyusul.)"
    ),
    MODE_PERSONAL: (
        "Kamu sedang dalam Personal Agent mode. "
        "(Placeholder Phase 4 — instruksi penuh menyusul.)"
    ),
}


@dataclass
class CommandResult:
    """Hasil parse slash command.

    is_command False → bukan command, teruskan ke LLM seperti biasa.
    action: "clear" | "scan" | "mode" | None — aksi UI yang harus
    dilakukan caller (agent_loop handle clear; TUI sync mode/model).
    """

    is_command: bool
    message: str = ""
    action: str | None = None


class ModeManager:
    """Pegang mode aktif + parse /command. Default: /code.

    `rescan_fn`: callback () -> str pesan display; dipasang app TUI
    agar /scan refresh project context + composer (lihat tui/app.py).
    Tanpa itu, /scan cuma return sinyal tanpa eksekusi.
    """

    def __init__(self, config: Config | None = None, soul: str = "",
                 rescan_fn: Callable[[], str] | None = None) -> None:
        self._mode = MODE_CODE
        self._config = config
        self._soul = soul
        self._rescan_fn = rescan_fn

    def get_mode(self) -> str:
        return self._mode

    def set_soul(self, soul: str) -> None:
        self._soul = soul

    def set_mode(self, mode: str) -> str:
        if mode not in (MODE_CODE, MODE_RESEARCH, MODE_PERSONAL):
            return f"❓ Mode tidak dikenal: {mode}. Pilihan: /code /research /personal"
        self._mode = mode
        return f"✅ Mode: {mode}"

    def get_mode_prompt(self) -> str:
        return MODE_PROMPTS[self._mode]

    def get_active_tools(self) -> list[str] | None:
        """Return None = semua tool aktif (code mode, Phase 2).

        research/personal belum bisa diaktifkan (placeholder),
        jadi cabang itu disiapkan untuk Phase 3/4.
        """
        return None

    @staticmethod
    def is_command(text: str) -> bool:
        return text.strip().startswith("/")

    def handle_command(self, user_input: str) -> CommandResult:
        text = user_input.strip()
        if not text.startswith("/"):
            return CommandResult(is_command=False)
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/code":
            return CommandResult(True, self.set_mode(MODE_CODE), "mode")
        if cmd == "/research":
            return CommandResult(True, "🔬 Research Agent belum tersedia (coming Phase 3) — tetap di mode code.", None)
        if cmd == "/personal":
            return CommandResult(True, "🏠 Personal Agent belum tersedia (coming Phase 4) — tetap di mode code.", None)
        if cmd == "/clear":
            return CommandResult(True, "🧹 History dibersihkan — mulai sesi baru.", "clear")
        if cmd == "/scan":
            if self._rescan_fn is None:
                return CommandResult(True, "🔍 Scan ulang belum wiring (jalan di TUI).", "scan")
            try:
                return CommandResult(True, self._rescan_fn(), "scan")
            except Exception as e:
                return CommandResult(True, f"❌ Scan gagal ({type(e).__name__}): {e}", None)
        if cmd == "/model":
            if not arg:
                current = self._config.model if self._config else "?"
                return CommandResult(True, f"🤖 Model aktif: {current}", None)
            if self._config is None:
                return CommandResult(True, "❌ Config tidak tersedia — model tidak bisa diganti.", None)
            if not arg.strip():
                return CommandResult(True, "❌ Nama model tidak boleh kosong.", None)
            self._config.model = arg.strip()
            return CommandResult(True, f"✅ Model diganti ke: {self._config.model}", "model")
        if cmd == "/help":
            return CommandResult(True, HELP_TEXT, None)
        if cmd == "/soul":
            return CommandResult(True, self._soul or "(soul kosong)", None)
        return CommandResult(True, f"❓ Command tidak dikenal: {parts[0]}. Ketik /help.", None)


if __name__ == "__main__":
    from core.config import Config as _Config

    cfg = _Config(model="m", api_key="k")
    mm = ModeManager(config=cfg, soul="soul-test")

    # 1. Default mode code + prompt-nya
    assert mm.get_mode() == "code"
    assert "Coding Agent" in mm.get_mode_prompt()
    assert mm.get_active_tools() is None  # semua tool aktif

    # 2. Bukan command → teruskan ke LLM
    r = mm.handle_command("halo, apa kabar?")
    assert r.is_command is False, r

    # 3. /code (case-insensitive) + /help + /soul
    assert mm.handle_command("/CODE").message == "✅ Mode: code"
    assert "/scan" in mm.handle_command("/help").message
    assert mm.handle_command("/soul").message == "soul-test"

    # 4. Placeholder tetap di code
    r = mm.handle_command("/research")
    assert "Phase 3" in r.message and mm.get_mode() == "code", (r, mm.get_mode())
    r = mm.handle_command("/personal")
    assert "Phase 4" in r.message and mm.get_mode() == "code", (r, mm.get_mode())

    # 5. /clear dan /scan kasih action signal
    assert mm.handle_command("/clear").action == "clear"
    assert mm.handle_command("/scan").action == "scan"

    # 6. /model lihat + ganti
    assert "m" in mm.handle_command("/model").message
    r = mm.handle_command("/model openai/gpt-4o")
    assert cfg.model == "openai/gpt-4o" and r.action == "model", (r, cfg.model)

    # 7. Unknown command + "/" kosong tidak crash
    assert "tidak dikenal" in mm.handle_command("/ngawur").message
    assert "tidak dikenal" in mm.handle_command("/").message

    # 8. Tanpa config: /model X ditolak dengan sopan
    mm2 = ModeManager()
    assert "tidak tersedia" in mm2.handle_command("/model x").message

    # 9. /scan tanpa callback → sinyal; dengan callback → pesan display
    assert mm2.handle_command("/scan").action == "scan"
    mm3 = ModeManager(rescan_fn=lambda: "🔍 demo · Python — context diperbarui.")
    r = mm3.handle_command("/scan")
    assert r.action == "scan" and "demo" in r.message, r
    mm4 = ModeManager(rescan_fn=lambda: (_ for _ in ()).throw(RuntimeError("disk")))
    assert "gagal" in mm4.handle_command("/scan").message.lower()

    print("✅ mode_manager self-test OK (9 skenario)")
