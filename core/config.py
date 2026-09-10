"""Config system (BYOK) — baca & validasi ~/.multacd/config.yaml.

Jalankan langsung untuk test cepat:
    python -m core.config
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

# Hormati MULTACD_HOME (isolation test) — konsisten dengan memory/store.py
# dan tools/agent/skill.py. Dievaluasi saat import; test set env sebelum subprocess.
CONFIG_DIR = Path(os.environ.get("MULTACD_HOME", str(Path.home()))) / ".multacd"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.yaml"
ENV_CONFIG_OVERRIDE = "MULTACD_CONFIG"

EXAMPLE_CONFIG = """\
# ~/.multacd/config.yaml — contoh config lengkap multacd (BYOK)

# ── Model (wajib diisi) ──────────────────────────────
model: "anthropic/claude-sonnet-4-6"
api_key: "sk-ant-xxxx"

# Contoh provider lain (uncomment salah satu):
#
# OpenAI
# model: "openai/gpt-4o"
# api_key: "sk-xxxx"
#
# Google Gemini
# model: "gemini/gemini-2.0-flash"
# api_key: "AIzaxxxx"
#
# Groq (cepat & murah)
# model: "groq/llama-3.3-70b-versatile"
# api_key: "gsk_xxxx"
#
# Ollama (lokal, gratis)
# model: "ollama/llama3.2"
# api_base: "http://localhost:11434"
# api_key: "none"
#
# Custom OpenAI-compatible endpoint
# model: "openai/nama-model"
# api_base: "https://endpoint-kamu.com/v1"
# api_key: "key-kamu"

# ── Agent Settings ───────────────────────────────────
max_tokens: 8096
temperature: 0.3
max_tool_iterations: 20      # batas loop per task, hindari infinite loop

# ── Permission Settings ──────────────────────────────
auto_approve_reads: true     # semua tool READ → langsung jalan
ask_before_write: true       # semua tool WRITE → konfirmasi dulu
ask_before_bash: true        # bash → konfirmasi dulu
ask_before_web: true         # web_fetch → konfirmasi dulu

# ── Display Settings ─────────────────────────────────
theme: "dark"                # dark | light | catppuccin-mocha | catppuccin-latte
                             # | catppuccin-frappe | catppuccin-macchiato
                             # (dark/light = alias mocha/latte)
show_tool_calls: true        # tampilkan nama tool yang dijalankan
show_thinking: false         # tampilkan reasoning LLM (verbose mode)
icon_style: "auto"           # auto | nerdfonts | unicode | ascii

# ── Search Provider (BYOK, Phase 3) ────────────────────
search_provider: "tavily"    # tavily | exa | brave | serpapi | duckduckgo
search_api_key: "tvly-xxxx"  # tidak perlu untuk duckduckgo (gratis, tidak resmi)

# ── Research Settings (Phase 3) ────────────────────────
search_results_per_query: 5     # hasil per query saat search
research_quick_queries: 3       # jumlah query untuk quick research
research_quick_max_sources: 5   # max sumber yang dibaca quick research
research_deep_rounds: 5         # max round untuk deep research
research_deep_queries_per_round: 4  # query per round di deep research
research_deep_max_sources: 20   # max total sumber deep research
research_scrape_timeout: 15     # timeout scraping per URL (detik)
research_snippet_fallback: true # pakai snippet kalau scraping gagal
"""


class Config(BaseModel):
    """Config utama multacd. Field flat 1:1 dengan contoh config.yaml."""

    # ── Model (wajib) ──
    model: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    api_base: str | None = None

    # ── Agent settings ──
    max_tokens: int = Field(default=8096, gt=0)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tool_iterations: int = Field(default=20, gt=0)

    # ── Permission settings ──
    auto_approve_reads: bool = True
    ask_before_write: bool = True
    ask_before_bash: bool = True
    ask_before_web: bool = True

    # ── Display settings ──
    theme: Literal["dark", "light", "catppuccin-mocha", "catppuccin-latte",
                   "catppuccin-frappe", "catppuccin-macchiato"] = "dark"
    show_tool_calls: bool = True
    show_thinking: bool = False
    icon_style: Literal["auto", "nerdfonts", "unicode", "ascii"] = "auto"

    # ── Search provider (BYOK, Phase 3) ──
    search_provider: Literal["tavily", "exa", "brave", "serpapi", "duckduckgo"] = "tavily"
    search_api_key: str = ""

    # ── Research settings (Phase 3) ──
    search_results_per_query: int = Field(default=5, gt=0)
    research_quick_queries: int = Field(default=3, gt=0)
    research_quick_max_sources: int = Field(default=5, gt=0)
    research_deep_rounds: int = Field(default=5, gt=0, le=10)
    research_deep_queries_per_round: int = Field(default=4, gt=0)
    research_deep_max_sources: int = Field(default=20, gt=0)
    research_scrape_timeout: int = Field(default=15, gt=0)
    research_snippet_fallback: bool = True

    @field_validator("search_provider", mode="before")
    @classmethod
    def _norm_provider(cls, v: object) -> object:
        # "Tavily", " TAVILY " → "tavily" (maafkan kapital/spasi user).
        return v.lower().strip() if isinstance(v, str) else v

    @field_validator("theme", mode="before")
    @classmethod
    def _norm_theme(cls, v: object) -> object:
        # "Dark", " MOCHA " → canonical ("dark", "mocha" bukan nama penuh
        # tetap ditolak pydantic dengan pesan jelas — cuma maafkan case).
        return v.lower().strip() if isinstance(v, str) else v


class ConfigError(Exception):
    """Error config yang friendly — pesannya bisa langsung ditampilkan ke user."""


# ── Active config sesi (Bug 3) ───────────────────────────────────────────
# Tool research (quick/deep_research, web_search, query_generator) tidak
# menerima config dari LLM — mereka membaca dari sini. MultacdApp memasang
# config-nya saat init, jadi `--config PATH` dan `/model X` tetap dihormati.
# None → fallback load_config() seperti dulu (pemakaian standalone/CLI).
_active_config: Config | None = None


def set_active_config(cfg: Config | None) -> None:
    """Pasang/cabut (None) config aktif sesi. Dipanggil MultacdApp saat init."""
    global _active_config
    _active_config = cfg


def get_active_config() -> Config | None:
    """Config sesi yang sedang jalan, atau None kalau tidak ada."""
    return _active_config


def resolve_config_path(explicit: Path | str | None = None) -> Path:
    """Urutan prioritas: argumen eksplisit > $MULTACD_CONFIG > ~/.multacd/config.yaml."""
    if explicit is not None:
        return Path(explicit).expanduser()
    env = os.environ.get(ENV_CONFIG_OVERRIDE)
    if env:
        return Path(env).expanduser()
    return DEFAULT_CONFIG_PATH


def _setup_message(path: Path) -> str:
    return (
        "⚡ multacd — config belum ditemukan.\n"
        "\n"
        f"File yang dicari: {path}\n"
        "\n"
        "Cara setup (sekali saja):\n"
        f"  1. Buat foldernya : mkdir -p {path.parent}\n"
        f"  2. Simpan contoh di bawah ini sebagai: {path}\n"
        "  3. Isi `model` dan `api_key` sesuai provider kamu (BYOK)\n"
        "  4. Jalankan lagi: python main.py\n"
        "\n"
        "────── contoh config ──────\n"
        f"{EXAMPLE_CONFIG}"
        "───────────────────────────\n"
    )


def load_config(explicit_path: Path | str | None = None) -> Config:
    """Baca & validasi config. Exit(1) dengan pesan jelas kalau ada masalah."""
    path = resolve_config_path(explicit_path)

    # Buat folder ~/.multacd/ kalau belum ada (aman dipanggil berulang).
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"❌ Gagal membuat folder config {path.parent}: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    if not path.is_file():
        print(_setup_message(path))
        raise SystemExit(1)

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"❌ config.yaml bukan YAML valid: {path}\n   Detail: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except OSError as e:
        print(f"❌ Gagal membaca config {path}: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    if not isinstance(raw, dict) or not raw:
        print(
            f"❌ config.yaml kosong atau tidak berbentuk key: value: {path}\n"
            "   Isi dengan contoh config (jalankan tanpa config untuk melihatnya).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        cfg = Config(**raw)
    except ValidationError as e:
        print(f"❌ config.yaml tidak valid: {path}", file=sys.stderr)
        for err in e.errors():
            field = ".".join(str(p) for p in err["loc"])
            print(f"   • {field}: {err['msg']}", file=sys.stderr)
        print("   Lihat contoh field yang benar di pesan setup.", file=sys.stderr)
        raise SystemExit(1) from e

    if not cfg.model.strip():
        print("❌ Field `model` wajib diisi (contoh: anthropic/claude-sonnet-4-6).", file=sys.stderr)
        raise SystemExit(1)
    if not cfg.api_key.strip():
        print("❌ Field `api_key` wajib diisi (BYOK — pakai key provider kamu).", file=sys.stderr)
        raise SystemExit(1)

    return cfg


def _mask_key(key: str) -> str:
    if len(key) <= 6:
        return "***"
    return f"{key[:4]}***{key[-2:]}"


if __name__ == "__main__":
    cfg = load_config()

    # Active config (Bug 3): set/get/clear simetris.
    set_active_config(cfg)
    assert get_active_config() is cfg
    set_active_config(None)
    assert get_active_config() is None

    print("✅ Config loaded OK")
    print(f"   model               : {cfg.model}")
    print(f"   api_key             : {_mask_key(cfg.api_key)}")
    print(f"   api_base            : {cfg.api_base or '(default provider)'}")
    print(f"   max_tokens          : {cfg.max_tokens}")
    print(f"   temperature         : {cfg.temperature}")
    print(f"   max_tool_iterations : {cfg.max_tool_iterations}")
    print(f"   theme               : {cfg.theme}")
