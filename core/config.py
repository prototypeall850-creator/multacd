"""Config system (BYOK) — baca & validasi ~/.multacd/config.yaml.

Jalankan langsung untuk test cepat:
    python -m core.config
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

# NOTE: tanpa pydantic — pydantic-core (Rust) tidak punya wheel Android
# (0 dari 159 rilis), jadi pydantic v2 mustahil diinstall di Termux.
# Validasi ditulis manual (dataclass + ConfigError), pesan tetap ramah.

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
theme: "dark"                # dark | light (= multacd-dark/light)
                             # + multacd-min (Termux hemat) | catppuccin-* (kompat v1)
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

# ── Telegram Bot (Phase 4, opsional) ───────────────────
# Diisi via setup wizard atau manual. Kosong = bot nonaktif.
# telegram:
#   bot_token: "123456:AAF..."  # dari @BotFather
#   admin_id: 123456789         # Telegram user ID kamu
#   admin_username: "usernamekamu"
#   allowed_users: [987654321]

# ── Scheduler (Phase 4, opsional) ──────────────────────
# schedules:
#   - name: "daily_briefing"
#     cron: "0 7 * * *"
#     action: "briefing"
#     channel: "telegram"

# ── Daily Briefing (Phase 4, opsional) ─────────────────
# briefing:
#   todo: true
#   git_status: true
#   news: true
#   news_topics: ["artificial intelligence"]
#   news_sources: 3
"""


class ConfigError(Exception):
    """Error config yang friendly — pesannya bisa langsung ditampilkan ke user."""

    def __init__(self, message: str, field_errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.field_errors = field_errors or []


THEMES = ("dark", "light", "multacd-dark", "multacd-light", "multacd-min",
          "catppuccin-mocha", "catppuccin-latte", "catppuccin-frappe",
          "catppuccin-macchiato")
ICON_STYLES = ("auto", "nerdfonts", "unicode", "ascii")
SEARCH_PROVIDERS = ("tavily", "exa", "brave", "serpapi", "duckduckgo")
SCHEDULE_ACTIONS = ("briefing", "research")


def _str(loc: str, v: object, errs: list[str], min_len: int = 0) -> str:
    # YAML `key:` kosong → None. Field opsional (min_len=0) maafkan jadi "",
    # field wajib tetap error tapi pesannya "wajib diisi", bukan "NoneType".
    if v is None:
        if min_len > 0:
            errs.append(f"{loc}: wajib diisi (kosong)")
        return ""
    if isinstance(v, bool) or not isinstance(v, (str, int, float)):
        errs.append(f"{loc}: harus teks, dapat {type(v).__name__}")
        return "" if isinstance(v, str) else str(v) if v is not None else ""
    s = v if isinstance(v, str) else str(v)
    if len(s) < min_len:
        errs.append(f"{loc}: wajib diisi (minimal {min_len} karakter)")
    return s


def _int(loc: str, v: object, errs: list[str], gt: int | None = None,
         le: int | None = None) -> int:
    n: int | None = None
    if v is None or (isinstance(v, str) and not v.strip()):
        n = 0  # key kosong = 0; lolos kalau opsional, error gt/le kalau wajib
    elif isinstance(v, int) and not isinstance(v, bool):
        n = v
    elif isinstance(v, str) and v.strip().lstrip("+-").isdigit():
        n = int(v.strip())
    if n is None:
        errs.append(f"{loc}: harus bilangan bulat, dapat {v!r}")
        return 0
    if gt is not None and not n > gt:
        errs.append(f"{loc}: harus > {gt}, dapat {n}")
    if le is not None and not n <= le:
        errs.append(f"{loc}: harus <= {le}, dapat {n}")
    return n


def _float(loc: str, v: object, errs: list[str], ge: float | None = None,
           le: float | None = None) -> float:
    f: float | None = None
    if v is None or (isinstance(v, str) and not v.strip()):
        f = 0.0  # key kosong = 0.0; lolos kalau opsional, error ge/le kalau wajib
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        f = float(v)
    elif isinstance(v, str):
        try:
            f = float(v.strip())
        except ValueError:
            f = None
    if f is None:
        errs.append(f"{loc}: harus angka, dapat {v!r}")
        return 0.0
    if ge is not None and not f >= ge:
        errs.append(f"{loc}: harus >= {ge}, dapat {f}")
    if le is not None and not f <= le:
        errs.append(f"{loc}: harus <= {le}, dapat {f}")
    return f


def _bool(loc: str, v: object, errs: list[str]) -> bool:
    if v is None:
        return False  # key kosong = default False (opsional)
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and v.strip().lower() in (
            "true", "1", "yes", "false", "0", "no"):
        return v.strip().lower() in ("true", "1", "yes")
    errs.append(f"{loc}: harus true/false, dapat {v!r}")
    return False


def _choice(loc: str, v: object, errs: list[str], options: tuple[str, ...],
            normalize: bool = False) -> str:
    if v is None:
        return options[0]  # key kosong = default opsi pertama
    s = v.lower().strip() if normalize and isinstance(v, str) else v
    if not isinstance(s, str) or s not in options:
        errs.append(f"{loc}: harus salah satu dari {', '.join(options)}, "
                    f"dapat {v!r}")
        return options[0] if isinstance(s, str) else ""
    return s


def _strmap(loc: str, v: object, errs: list[str]) -> dict[str, str]:
    """Dict str→str (provider_keys/bases). None → {}. Key dilower-case,
    value kosong dibuang. Bukan mapping / value bukan str = error."""
    if v is None:
        return {}
    if not isinstance(v, dict):
        errs.append(f"{loc}: harus mapping, dapat {type(v).__name__}")
        return {}
    out: dict[str, str] = {}
    for k, val in v.items():
        if not isinstance(k, str) or not isinstance(val, str):
            errs.append(f"{loc}.{k}: key dan value harus teks")
            continue
        if val.strip():
            out[k.lower().strip()] = val
    return out


def _raise_if_errors(errs: list[str]) -> None:
    if errs:
        raise ConfigError("config tidak valid: " + "; ".join(errs), errs)


@dataclass
class TelegramConfig:
    """Kredensial bot + whitelist (Phase 4). Default kosong = nonaktif."""

    bot_token: str = ""
    admin_id: int = 0
    admin_username: str = ""
    allowed_users: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Normalisasi None sudah ditangani _str/_int (key kosong → default).
        errs: list[str] = []
        self.bot_token = _str("telegram.bot_token", self.bot_token, errs)
        self.admin_id = _int("telegram.admin_id", self.admin_id, errs)
        self.admin_username = _str("telegram.admin_username",
                                   self.admin_username, errs)
        if self.allowed_users is None:
            self.allowed_users = []  # `allowed_users:` kosong = []
        if not isinstance(self.allowed_users, list):
            errs.append(f"telegram.allowed_users: harus list, "
                        f"dapat {self.allowed_users!r}")
            self.allowed_users = []
        else:
            fixed = []
            for i, uid in enumerate(self.allowed_users):
                fixed.append(_int(f"telegram.allowed_users[{i}]", uid, errs))
            self.allowed_users = fixed
        _raise_if_errors(errs)


@dataclass
class ScheduleConfig:
    """Satu jadwal cron (Phase 4). channel: telegram (saat ini satu-satunya)."""

    name: str = ""
    cron: str = ""
    action: str = "briefing"
    topic: str = ""
    channel: str = "telegram"

    def __post_init__(self) -> None:
        errs: list[str] = []
        self.name = _str("schedule.name", self.name, errs, min_len=1)
        self.cron = _str("schedule.cron", self.cron, errs, min_len=1)
        self.action = _choice("schedule.action", self.action, errs,
                              SCHEDULE_ACTIONS)
        self.topic = _str("schedule.topic", self.topic, errs)
        self.channel = _str("schedule.channel", self.channel, errs)
        _raise_if_errors(errs)


@dataclass
class BriefingConfig:
    """Konten daily briefing (Phase 4)."""

    todo: bool = True
    news: bool = True
    git_status: bool = True
    weather: bool = False  # Phase 5 (butuh API cuaca)
    news_topics: list[str] = field(
        default_factory=lambda: ["artificial intelligence",
                                 "software engineering"])
    news_sources: int = 3

    def __post_init__(self) -> None:
        errs: list[str] = []
        self.todo = _bool("briefing.todo", self.todo, errs)
        self.news = _bool("briefing.news", self.news, errs)
        self.git_status = _bool("briefing.git_status", self.git_status, errs)
        self.weather = _bool("briefing.weather", self.weather, errs)
        if self.news_topics is None:
            self.news_topics = ["artificial intelligence",
                                "software engineering"]
        if not isinstance(self.news_topics, list) or not all(
                isinstance(t, str) for t in self.news_topics):
            errs.append("briefing.news_topics: harus list of string")
            self.news_topics = []
        self.news_sources = _int("briefing.news_sources", self.news_sources,
                                 errs, gt=0)
        _raise_if_errors(errs)


def _nested(loc: str, cls: type, v: object, errs: list[str]) -> object:
    """Dict → dataclass nested. Error nested digabung ke errs caller."""
    if isinstance(v, cls):
        return v
    if v is None:
        return cls()  # `telegram:` kosong tanpa isi = pakai default (nonaktif)
    if isinstance(v, dict):
        known = {f.name for f in fields(cls)}
        try:
            return cls(**{k: val for k, val in v.items() if k in known})
        except ConfigError as e:
            errs.extend(e.field_errors)
            return cls()
    errs.append(f"{loc}: harus mapping, dapat {type(v).__name__}")
    return cls()


@dataclass
class Config:
    """Config utama multacd. Field flat 1:1 dengan contoh config.yaml."""

    # ── Model (wajib) ──
    model: str = ""
    api_key: str = ""
    api_base: str | None = None
    # Key/base per provider (#31): {"openai": "sk-...", ...}. Dipakai saat
    # model pindah provider; fallback = api_key/api_base top-level.
    provider_keys: dict = field(default_factory=dict)
    provider_bases: dict = field(default_factory=dict)

    # ── Agent settings ──
    max_tokens: int = 8096
    temperature: float = 0.3
    max_tool_iterations: int = 20

    # ── Permission settings ──
    auto_approve_reads: bool = True
    ask_before_write: bool = True
    ask_before_bash: bool = True
    ask_before_web: bool = True

    # ── Display settings ──
    theme: str = "dark"
    show_tool_calls: bool = True
    show_thinking: bool = False
    icon_style: str = "auto"

    # ── Search provider (BYOK, Phase 3) ──
    search_provider: str = "tavily"
    search_api_key: str = ""

    # ── Research settings (Phase 3) ──
    search_results_per_query: int = 5
    research_quick_queries: int = 3
    research_quick_max_sources: int = 5
    research_deep_rounds: int = 5
    research_deep_queries_per_round: int = 4
    research_deep_max_sources: int = 20
    research_scrape_timeout: int = 15
    research_snippet_fallback: bool = True

    # ── Personal agent (Phase 4, opsional) ──
    telegram: TelegramConfig = field(default_factory=TelegramConfig)  # type: ignore[assignment]
    schedules: list = field(default_factory=list)
    briefing: BriefingConfig = field(default_factory=BriefingConfig)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        errs: list[str] = []
        self.model = _str("model", self.model, errs, min_len=1)
        self.api_key = _str("api_key", self.api_key, errs, min_len=1)
        if self.api_base is not None:
            self.api_base = _str("api_base", self.api_base, errs)
        self.provider_keys = _strmap("provider_keys", self.provider_keys,
                                     errs)
        self.provider_bases = _strmap("provider_bases", self.provider_bases,
                                      errs)
        self.max_tokens = _int("max_tokens", self.max_tokens, errs, gt=0)
        self.temperature = _float("temperature", self.temperature, errs,
                                  ge=0.0, le=2.0)
        self.max_tool_iterations = _int("max_tool_iterations",
                                        self.max_tool_iterations, errs, gt=0)
        self.auto_approve_reads = _bool("auto_approve_reads",
                                        self.auto_approve_reads, errs)
        self.ask_before_write = _bool("ask_before_write",
                                      self.ask_before_write, errs)
        self.ask_before_bash = _bool("ask_before_bash",
                                     self.ask_before_bash, errs)
        self.ask_before_web = _bool("ask_before_web", self.ask_before_web,
                                    errs)
        # "Dark", " MOCHA " → maafkan case/spasi; nama pendek non-kanonis
        # tetap ditolak dengan pesan jelas.
        self.theme = _choice("theme", self.theme, errs, THEMES,
                             normalize=True)
        self.show_tool_calls = _bool("show_tool_calls", self.show_tool_calls,
                                     errs)
        self.show_thinking = _bool("show_thinking", self.show_thinking, errs)
        self.icon_style = _choice("icon_style", self.icon_style, errs,
                                  ICON_STYLES)
        # "Tavily", " TAVILY " → "tavily" (maafkan kapital/spasi user).
        self.search_provider = _choice("search_provider", self.search_provider,
                                       errs, SEARCH_PROVIDERS, normalize=True)
        self.search_api_key = _str("search_api_key", self.search_api_key,
                                   errs)
        self.search_results_per_query = _int("search_results_per_query",
                                             self.search_results_per_query,
                                             errs, gt=0)
        self.research_quick_queries = _int("research_quick_queries",
                                           self.research_quick_queries,
                                           errs, gt=0)
        self.research_quick_max_sources = _int(
            "research_quick_max_sources", self.research_quick_max_sources,
            errs, gt=0)
        self.research_deep_rounds = _int("research_deep_rounds",
                                         self.research_deep_rounds,
                                         errs, gt=0, le=10)
        self.research_deep_queries_per_round = _int(
            "research_deep_queries_per_round",
            self.research_deep_queries_per_round, errs, gt=0)
        self.research_deep_max_sources = _int("research_deep_max_sources",
                                              self.research_deep_max_sources,
                                              errs, gt=0)
        self.research_scrape_timeout = _int("research_scrape_timeout",
                                            self.research_scrape_timeout,
                                            errs, gt=0)
        self.research_snippet_fallback = _bool("research_snippet_fallback",
                                               self.research_snippet_fallback,
                                               errs)
        self.telegram = _nested("telegram", TelegramConfig,
                                self.telegram, errs)
        if self.schedules is None:
            self.schedules = []  # `schedules:` kosong = []
        if not isinstance(self.schedules, list):
            errs.append(f"schedules: harus list, "
                        f"dapat {type(self.schedules).__name__}")
            self.schedules = []
        else:
            fixed = []
            for i, item in enumerate(self.schedules):
                if isinstance(item, ScheduleConfig):
                    fixed.append(item)
                elif isinstance(item, dict):
                    known = {f.name for f in fields(ScheduleConfig)}
                    try:
                        fixed.append(ScheduleConfig(
                            **{k: v for k, v in item.items()
                               if k in known}))
                    except ConfigError as e:
                        # Item invalid dilaporkan; Config.__post_init__
                        # raise di akhir (errs tak kosong), jadi item
                        # ini memang tidak dipakai.
                        errs.extend(
                            f"schedules[{i}].{fe.split('.', 1)[1]}"
                            if fe.startswith("schedule.") else
                            f"schedules[{i}].{fe}"
                            for fe in e.field_errors)
                else:
                    errs.append(f"schedules[{i}]: harus mapping, "
                                f"dapat {type(item).__name__}")
            self.schedules = fixed
        self.briefing = _nested("briefing", BriefingConfig,
                                self.briefing, errs)
        _raise_if_errors(errs)


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
        "multacd — config belum ditemukan.\n"
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


def config_from_dict(raw: dict) -> Config:
    """Dict (YAML/wizard) → Config. Key asing diabaikan (forward-compat)."""
    known = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in raw.items() if k in known})


def save_config_updates(updates: dict,
                        explicit_path: Path | str | None = None) -> None:
    """Merge updates ke config.yaml lalu tulis (buat /model /key /base).

    Dict di-merge per-key (provider_keys lama dipertahankan), sisanya
    replace. Raise OSError kalau gagal tulis — caller yang berpesan.
    """
    path = resolve_config_path(explicit_path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(raw.get(k), dict):
            merged = dict(raw[k])
            for mk, mv in v.items():
                # "" / None = hapus key (dipakai `/base -`).
                if mv is None or (isinstance(mv, str) and not mv.strip()):
                    merged.pop(mk, None)
                else:
                    merged[mk] = mv
            raw[k] = merged
        else:
            raw[k] = v
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
                    encoding="utf-8")


def load_config(explicit_path: Path | str | None = None) -> Config:
    """Baca & validasi config. Exit(1) dengan pesan jelas kalau ada masalah."""
    path = resolve_config_path(explicit_path)

    # Buat folder ~/.multacd/ kalau belum ada (aman dipanggil berulang).
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Gagal membuat folder config {path.parent}: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    if not path.is_file():
        print(_setup_message(path))
        raise SystemExit(1)

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"config.yaml bukan YAML valid: {path}\n   Detail: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except OSError as e:
        print(f"Gagal membaca config {path}: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    if not isinstance(raw, dict) or not raw:
        print(
            f"config.yaml kosong atau tidak berbentuk key: value: {path}\n"
            "   Isi dengan contoh config (jalankan tanpa config untuk melihatnya).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        cfg = config_from_dict(raw)
    except ConfigError as e:
        print(f"config.yaml tidak valid: {path}", file=sys.stderr)
        for line in e.field_errors:
            print(f"   • {line}", file=sys.stderr)
        print("   Lihat contoh field yang benar di pesan setup.", file=sys.stderr)
        raise SystemExit(1) from e

    if not cfg.model.strip():
        print("Field `model` wajib diisi (contoh: anthropic/claude-sonnet-4-6).", file=sys.stderr)
        raise SystemExit(1)
    if not cfg.api_key.strip():
        print("Field `api_key` wajib diisi (BYOK — pakai key provider kamu).", file=sys.stderr)
        raise SystemExit(1)

    return cfg


def _mask_key(key: str) -> str:
    if len(key) <= 6:
        return "***"
    return f"{key[:4]}***{key[-2:]}"


if __name__ == "__main__":
    # Hermetic: tulis config contoh ke dir isolasi (jangan baca config
    # asli user — isinya beda-beda, assert di bawah harus deterministik).
    import tempfile as _tempfile

    _iso = Path(_tempfile.mkdtemp(prefix="multacd-cfgtest-"))
    _cfg_path = _iso / "config.yaml"
    _cfg_path.write_text(
        "model: groq/llama-3.3-70b-versatile\napi_key: gsk-x\n"
        "search_provider: ' Tavily '\ntheme: Dark\n"
        "telegram:\n  bot_token: t\n  admin_id: 1\n  admin_username: u\n"
        "  allowed_users: [2]\n"
        "schedules:\n  - name: j\n    cron: '0 7 * * *'\n"
        "    action: briefing\n"
        "kunci_asing: abaikan gue\n",
        encoding="utf-8")
    cfg = load_config(_cfg_path)

    # Active config (Bug 3): set/get/clear simetris.
    set_active_config(cfg)
    assert get_active_config() is cfg
    set_active_config(None)
    assert get_active_config() is None

    # Normalisasi + nested parse dari YAML.
    assert cfg.search_provider == "tavily", cfg.search_provider
    assert cfg.theme == "dark", cfg.theme
    assert cfg.telegram.admin_id == 1 and cfg.telegram.allowed_users == [2]
    assert cfg.schedules[0].cron == "0 7 * * *"

    # Phase 4: nested default + parse dari dict.
    legacy = Config(model="m", api_key="k")  # yaml lama tanpa phase4
    assert legacy.telegram.bot_token == "" and legacy.schedules == []
    assert legacy.telegram.admin_id == 0 and legacy.briefing.todo
    assert legacy.briefing.news_sources == 3
    full = Config(model="m", api_key="k", telegram={
        "bot_token": "t", "admin_id": 1, "admin_username": "u",
        "allowed_users": [2]},
        schedules=[{"name": "j", "cron": "0 7 * * *",
                     "action": "briefing"}])
    assert full.telegram.admin_id == 1 and full.schedules[0].cron == "0 7 * * *"

    # Invalid: satu ConfigError berisi SEMUA field bermasalah.
    try:
        Config(model="  ", api_key="k", search_provider="google",
               temperature=9, research_deep_rounds=99,
               schedules=[{"name": "", "action": "party"}])
        raise AssertionError("config invalid harus ditolak")
    except ConfigError as e:
        for needle in ("search_provider", "temperature",
                       "research_deep_rounds", "schedules[0].name",
                       "schedules[0].action"):
            assert needle in str(e), (needle, str(e)[:200])

    print("✅ Config loaded OK")
    print(f"   model               : {cfg.model}")
    print(f"   api_key             : {_mask_key(cfg.api_key)}")
    print(f"   api_base            : {cfg.api_base or '(default provider)'}")
    print(f"   max_tokens          : {cfg.max_tokens}")
    print(f"   temperature         : {cfg.temperature}")
    print(f"   max_tool_iterations : {cfg.max_tool_iterations}")
    print(f"   theme               : {cfg.theme}")
