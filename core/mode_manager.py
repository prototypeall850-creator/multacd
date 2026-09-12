"""Mode manager — mode agent + parse slash command.

Mode aktif:
    code      → Coding Agent (penuh di Phase 2)
    research  → Research Agent (penuh di Phase 3)
    personal  → Personal Agent (penuh di Phase 4)

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
    "Command multacd:\n"
    "  /code          → mode Coding Agent (default)\n"
    "  /research      → mode Research Agent (riset internet + sumber)\n"
    "  /personal      → Personal Agent (bot, jadwal, briefing, daemon)\n"
    "  /clear         → bersihkan history, mulai sesi baru\n"
    "  /scan          → scan ulang codebase project\n"
    "  /model [nama]  → lihat / ganti model (cth: /model openai/gpt-4o)\n"
    "  /models [prov] → jelajahi model satu provider\n"
    "  /connect [prov]→ sambung provider (pasang key via dialog)\n"
    "  /key [KEY]     → lihat / pasang API key provider aktif\n"
    "  /base [URL]    → lihat / pasang endpoint provider aktif\n"
    "  /soul          → tampilkan kepribadian agent yang aktif\n"
    "  /help          → tampilkan pesan ini"
)

# Single source buat slash palette (nama + deskripsi singkat).
PALETTE_COMMANDS: tuple[tuple[str, str], ...] = (
    ("/code", "Switch to Coding Agent mode"),
    ("/research", "Switch to Research Agent mode"),
    ("/personal", "Switch to Personal Agent mode"),
    ("/clear", "Clear conversation history"),
    ("/scan", "Re-scan codebase"),
    ("/model", "Switch LLM model"),
    ("/models", "Browse provider models"),
    ("/connect", "Connect a provider"),
    ("/key", "Set provider API key"),
    ("/base", "Set provider endpoint"),
    ("/soul", "Show active soul.md"),
    ("/help", "Show all commands"),
)

# Command yang butuh argumen lanjutan → Enter = autocomplete, bukan submit.
COMMANDS_WITH_ARGS = frozenset({"/model", "/models", "/connect", "/key", "/base"})

MODE_PROMPTS = {
    MODE_CODE: (
        "Kamu sedang dalam Coding Agent mode. "
        "Kamu punya akses ke: filesystem, shell, git, "
        "run_python, lint_python, run_tests. "
        "Fokus membantu user dengan kode dan development workflow. "
        "Smart commit flow: user minta commit → jalankan git_status + git_diff dulu, "
        "tulis pesan conventional commits (feat/fix/refactor/docs/chore), "
        "lalu git_add + git_commit (dialog konfirmasi = persetujuan user). "
        "Jangan push ke branch main/master/production/prod/release/stable "
        "tanpa izin eksplisit — kalau tool menolak, tawarkan ke user: "
        "tetap push, buat branch baru, atau batal. "
        "Kalau merge conflict: analisis ours-vs-theirs, suggest resolusi, "
        "apply via edit_file + git_add hanya setelah user setuju. "
        "Kalau run_python/lint_python/run_tests gagal atau error: baca output-nya, "
        "jelaskan penyebab ke user, suggest fix — jangan auto-fix tanpa izin."
    ),
    MODE_RESEARCH: (
        "Kamu sedang dalam Research Agent mode. "
        "Kamu punya akses ke: web_search, web_scrape, quick_research, "
        "deep_research, export_research. "
        "Panduan: untuk pertanyaan butuh jawaban cepat dengan sumber → "
        "quick_research; untuk topik kompleks butuh laporan mendalam → "
        "deep_research. Selalu kutip sumber dalam jawaban. "
        "Kalau scraping gagal, gunakan snippet dan beritahu user. "
        "Tawarkan export ke .md setelah research selesai. "
        "Deteksi dan flag informasi yang kontradiktif antar sumber."
    ),
    MODE_PERSONAL: (
        "Kamu sedang dalam Personal Agent mode. "
        "Kamu punya akses ke: send_telegram, schedule_job, cancel_job, "
        "get_jobs, daemon_status, user_manager, generate_briefing, "
        "web_search, quick_research, read tools, git_status, remember, "
        "recall. "
        "Tugasmu: kelola bot Telegram (tambah/hapus user), kelola scheduled "
        "jobs, cek status daemon, buat & kirim briefing, kirim pesan manual. "
        "Aturan: aksi berdampak (tambah/hapus user, schedule/cancel, kirim "
        "pesan/file, generate briefing) selalu konfirmasi dulu — tool sudah "
        "ASK, hormati jawaban user. "
        "'Kirim briefing sekarang' = konfirmasi, lalu generate_briefing "
        "(send_to_admin=True kalau user mau dikirim ke Telegram). "
        "Jangan panggil tool yang tidak ada di daftar."
    ),
}

# Tool aktif di mode /personal: personal tools + baca + riset ringan.
# Tulis/shell/eksekusi TIDAK ada — mode ini dashboard manajemen, aman.
PERSONAL_MODE_TOOLS = [
    "send_telegram",
    "schedule_job",
    "cancel_job",
    "get_jobs",
    "daemon_status",
    "user_manager",
    "generate_briefing",
    "web_search",
    "quick_research",
    "read_file",
    "read_many_files",
    "glob",
    "grep",
    "list_dir",
    "scan_codebase",
    "git_status",
    "remember",
    "recall",
]

# Tool aktif di mode /research: research tools + read tools Phase 1
# (web_fetch, read_file, dll tetap aktif — lihat PLAN-phase3 §10).
RESEARCH_MODE_TOOLS = [
    "web_search",
    "web_scrape",
    "quick_research",
    "deep_research",
    "export_research",
    "read_file",
    "read_many_files",
    "glob",
    "grep",
    "list_dir",
    "scan_codebase",
    "web_fetch",
]


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
        self._git_enabled = True

    def set_git_enabled(self, enabled: bool) -> None:
        """Matikan kalau folder bukan git repo → tool git disembunyikan."""
        self._git_enabled = enabled

    def get_mode(self) -> str:
        return self._mode

    def set_soul(self, soul: str) -> None:
        self._soul = soul

    def set_mode(self, mode: str) -> str:
        if mode not in (MODE_CODE, MODE_RESEARCH, MODE_PERSONAL):
            return f"Mode tidak dikenal: {mode}. Pilihan: /code /research /personal"
        self._mode = mode
        return f"Mode: {mode}"

    def get_mode_prompt(self) -> str:
        return MODE_PROMPTS[self._mode]

    def get_active_tools(self) -> list[str] | None:
        """None = semua tool aktif. Bukan git repo → list tanpa tool git.

        Mode /research → list eksplisit (research + read tools).
        """
        if self._mode == MODE_RESEARCH:
            return list(RESEARCH_MODE_TOOLS)
        if self._mode == MODE_PERSONAL:
            return list(PERSONAL_MODE_TOOLS)
        if self._git_enabled:
            return None
        from core.permissions import GIT_TOOLS, KNOWN_TOOLS
        return sorted(KNOWN_TOOLS - GIT_TOOLS)

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
            msg = self.set_mode(MODE_RESEARCH)
            return CommandResult(
                True,
                f"{msg} — tanya apa saja, jawaban berkutipan sumber. "
                "Ctrl+R panel sumber.",
                "mode")
        if cmd == "/personal":
            msg = self.set_mode(MODE_PERSONAL)
            try:
                from tools.personal.daemon_status import daemon_status
                snapshot = daemon_status()["result"]
            except Exception as e:
                snapshot = f"(status daemon gagal dibaca: {e})"
            return CommandResult(
                True,
                f"{msg} — kelola bot, jadwal, briefing, daemon.\n"
                f"{snapshot}",
                "mode")
        if cmd == "/clear":
            return CommandResult(True, "History dibersihkan — mulai sesi baru.", "clear")
        if cmd == "/scan":
            if self._rescan_fn is None:
                return CommandResult(True, "Scan ulang belum wiring (jalan di TUI).", "scan")
            try:
                return CommandResult(True, self._rescan_fn(), "scan")
            except Exception as e:
                return CommandResult(True, f"Scan gagal ({type(e).__name__}): {e}", None)
        if cmd == "/model":
            if not arg:
                current = self._config.model if self._config else "?"
                return CommandResult(True, f"Model aktif: {current}", None)
            if self._config is None:
                return CommandResult(True, "Config tidak tersedia — model tidak bisa diganti.", None)
            if not arg.strip():
                return CommandResult(True, "Nama model tidak boleh kosong.", None)
            return self._switch_model(arg.strip())
        if cmd == "/key":
            return self._handle_key(arg)
        if cmd == "/base":
            return self._handle_base(arg)
        if cmd == "/connect":
            return CommandResult(
                True, "`/connect` butuh dialog TUI — jalan di aplikasi, "
                "bukan mode headless.", None)
        if cmd == "/models":
            return CommandResult(
                True, "`/models` buka popup di TUI (atau Ctrl+O). "
                "Headless: `/model provider/nama` langsung.", None)
        if cmd == "/help":
            return CommandResult(True, HELP_TEXT, None)
        if cmd == "/soul":
            return CommandResult(True, self._soul or "(soul kosong)", None)
        return CommandResult(True, f"Command tidak dikenal: {parts[0]}. Ketik /help.", None)

    @staticmethod
    def _mask(key: str) -> str:
        return "***" if len(key) <= 6 else f"{key[:4]}***{key[-2:]}"

    def _persist(self, updates: dict) -> str:
        """Simpan ke config.yaml. Return "" ok, else pesan error."""
        if self._config is None:
            return " (config tak tersedia — hanya sesi ini)"
        try:
            from core.config import save_config_updates
            save_config_updates(updates)
        except OSError as e:
            return f" (gagal simpan config: {e} — hanya sesi ini)"
        return ""

    def _switch_model(self, name: str) -> CommandResult:
        """Ganti model + persist. Pindah provider tanpa key → warning.

        Key/base lama TIDAK dibawa (dulu 401 diam-diam). Kredensial yang
        dipakai = provider_keys[prov] atau top-level (lihat llm_client).
        """
        from core.providers import provider_id_of
        assert self._config is not None
        old_prov = provider_id_of(self._config.model)
        new_prov = provider_id_of(name)
        self._config.model = name
        note = self._persist({"model": name})
        msg = f"Model diganti ke: {name}{note}"
        if new_prov and new_prov != old_prov \
                and new_prov not in self._config.provider_keys:
            if old_prov and old_prov not in self._config.provider_keys:
                # Setup satu key: top-level milik provider lama → 401 pasti.
                msg += (f"\nKey top-level milik `{old_prov}` — `{new_prov}` "
                        f"butuh key sendiri: `/key KEY`.")
            else:
                msg += (f"\n`{new_prov}` pakai key top-level — kalau API "
                        f"menolak (401), pasang via `/key KEY`.")
            if new_prov not in ("openai", "anthropic", "gemini", "groq",
                                "deepseek", "ollama") \
                    and new_prov not in self._config.provider_bases \
                    and not self._config.api_base:
                msg += " Endpoint custom? `/base URL` dulu."
        return CommandResult(True, msg, "model")

    def _handle_key(self, arg: str) -> CommandResult:
        """Lihat/pasang API key provider dari model aktif."""
        from core.providers import provider_id_of
        if self._config is None:
            return CommandResult(True, "Config tidak tersedia.", None)
        prov = provider_id_of(self._config.model) or "(default)"
        if not arg.strip():
            saved = self._config.provider_keys.get(prov, "")
            cur = saved or self._config.api_key
            have = f"{self._mask(cur)} ({'per-provider' if saved else 'top-level'})" if cur else "(belum ada)"
            return CommandResult(True, f"Key `{prov}`: {have}. Pasang: /key KEY", None)
        key = arg.strip()
        if prov == "(default)":
            self._config.api_key = key
            note = self._persist({"api_key": key})
            return CommandResult(True, f"Key default disimpan{note}.", "model")
        self._config.provider_keys[prov] = key
        note = self._persist({"provider_keys": {prov: key}})
        return CommandResult(True, f"Key `{prov}` disimpan{note}.", "model")

    def _handle_base(self, arg: str) -> CommandResult:
        """Lihat/pasang endpoint provider dari model aktif."""
        from core.providers import provider_id_of
        if self._config is None:
            return CommandResult(True, "Config tidak tersedia.", None)
        prov = provider_id_of(self._config.model) or "(default)"
        if not arg.strip():
            saved = self._config.provider_bases.get(prov, "")
            cur = saved or self._config.api_base or "(bawaan provider)"
            src = "per-provider" if saved else ("top-level" if self._config.api_base else "bawaan")
            return CommandResult(True, f"Endpoint `{prov}`: {cur} ({src}). Pasang: /base URL, hapus: /base -", None)
        if arg.strip() == "-":
            if prov == "(default)":
                self._config.api_base = None
                note = self._persist({"api_base": None})
            else:
                self._config.provider_bases.pop(prov, None)
                note = self._persist({"provider_bases": {prov: ""}})
            return CommandResult(True, f"Endpoint `{prov}` dihapus{note}.", "model")
        base = arg.strip().rstrip("/")
        if prov == "(default)":
            self._config.api_base = base
            note = self._persist({"api_base": base})
        else:
            self._config.provider_bases[prov] = base
            note = self._persist({"provider_bases": {prov: base}})
        return CommandResult(True, f"Endpoint `{prov}` → {base}{note}.", "model")


if __name__ == "__main__":
    import os as _os
    import tempfile as _tf

    from core.config import Config as _Config

    # /model /key /base persist ke file — isolasi ke tmp (jangan sentuh
    # config asli user).
    _os.environ["MULTACD_CONFIG"] = str(
        __import__("pathlib").Path(_tf.mkdtemp(prefix="multacd-mm-"))
        / "config.yaml")
    from core.config import save_config_updates as _save
    _save({"model": "m", "api_key": "k"})  # reload di 6b butuh api_key

    cfg = _Config(model="m", api_key="k")
    mm = ModeManager(config=cfg, soul="soul-test")

    # 1. Default mode code + prompt-nya
    assert mm.get_mode() == "code"
    assert "Coding Agent" in mm.get_mode_prompt()
    assert "conventional" in mm.get_mode_prompt()  # smart commit flow
    assert mm.get_active_tools() is None  # semua tool aktif
    mm.set_git_enabled(False)
    active = mm.get_active_tools()
    assert active is not None and not any(t.startswith("git_") for t in active), active
    assert "read_file" in active and "bash" in active
    mm.set_git_enabled(True)
    assert mm.get_active_tools() is None

    # 2. Bukan command → teruskan ke LLM
    r = mm.handle_command("halo, apa kabar?")
    assert r.is_command is False, r

    # 3. /code (case-insensitive) + /help + /soul
    assert mm.handle_command("/CODE").message == "Mode: code"
    assert "/scan" in mm.handle_command("/help").message
    assert mm.handle_command("/soul").message == "soul-test"

    # 4. /research aktif (Phase 3); /personal aktif (Phase 4)
    r = mm.handle_command("/research")
    assert mm.get_mode() == "research" and r.action == "mode", (r, mm.get_mode())
    assert "quick_research" in mm.get_mode_prompt()
    active = mm.get_active_tools()
    assert active is not None and "quick_research" in active, active
    assert "deep_research" in active and "web_search" in active
    assert "read_file" in active and "web_fetch" in active
    assert "git_commit" not in active and "bash" not in active
    mm.handle_command("/code")
    assert mm.get_mode() == "code" and mm.get_active_tools() is None
    r = mm.handle_command("/personal")
    assert mm.get_mode() == "personal" and r.action == "mode", (r, mm.get_mode())
    assert "Daemon:" in r.message, r.message  # snapshot status ikut
    assert "Personal Agent" in mm.get_mode_prompt()
    active = mm.get_active_tools()
    assert active is not None and "daemon_status" in active, active
    assert "user_manager" in active and "generate_briefing" in active
    assert "get_jobs" in active and "send_telegram" in active
    assert "bash" not in active and "write_file" not in active  # aman
    assert "delete_file" not in active and "run_python" not in active
    mm.handle_command("/code")
    assert mm.get_mode() == "code"

    # 5. /clear dan /scan kasih action signal
    assert mm.handle_command("/clear").action == "clear"
    assert mm.handle_command("/scan").action == "scan"

    # 6. /model lihat + ganti (persist ke file isolasi)
    assert "m" in mm.handle_command("/model").message
    r = mm.handle_command("/model openai/gpt-4o")
    assert cfg.model == "openai/gpt-4o" and r.action == "model", (r, cfg.model)
    assert "Model diganti ke: openai/gpt-4o" in r.message, r.message

    # 6b. Pindah provider tanpa key → warning (dulu 401 diam-diam, #31).
    # cfg single-key: top-level milik "m" (prov "") → openai = provider baru.
    mm_b = ModeManager(config=_Config(model="groq/llama-3.3-70b-versatile",
                                      api_key="gsk-x"))
    r = mm_b.handle_command("/model anthropic/claude-haiku-4-5")
    assert r.action == "model" and "/key" in r.message, r.message
    # Pasang key → pindah lagi diam (key sudah ada).
    r = mm_b.handle_command("/key sk-ant-yyy")
    assert r.action == "model" and "anthropic" in r.message, r.message
    assert mm_b._config.provider_keys["anthropic"] == "sk-ant-yyy"
    r = mm_b.handle_command("/model anthropic/claude-sonnet-4-6")
    assert "/key" not in r.message, r.message
    # /key lihat (mask) + /base pasang/hapus.
    assert "sk-ant" not in mm_b.handle_command("/key").message
    assert "***" in mm_b.handle_command("/key").message
    r = mm_b.handle_command("/base https://proxy.local/v1/")
    assert "proxy.local/v1" in r.message, r.message
    assert mm_b._config.provider_bases["anthropic"] == "https://proxy.local/v1"
    r = mm_b.handle_command("/base -")
    assert "dihapus" in r.message and "anthropic" not in mm_b._config.provider_bases
    # Persist betulan: baca ulang file → model + key ada.
    from core.config import load_config as _load
    reloaded = _load()
    assert reloaded.model == "anthropic/claude-sonnet-4-6", reloaded.model
    assert reloaded.provider_keys.get("anthropic") == "sk-ant-yyy"

    # 7. Unknown command + "/" kosong tidak crash
    assert "tidak dikenal" in mm.handle_command("/ngawur").message
    assert "tidak dikenal" in mm.handle_command("/").message
    # /connect + /models butuh TUI — headless dapat pesan jujur.
    assert "TUI" in mm.handle_command("/connect").message
    assert "Ctrl+O" in mm.handle_command("/models").message
    assert "/connect" in mm.handle_command("/help").message
    assert "/models" in mm.handle_command("/help").message

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

    print("✅ mode_manager self-test OK (10 skenario + key/base)")
