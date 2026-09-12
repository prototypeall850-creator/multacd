"""Provider LLM native — pengganti LiteLLM (lihat core/llm_client.py).

Dua adapter menutup 6 provider wizard (full OpenAI-compatible + Anthropic).
Ringan: cuma butuh httpx (wheel murni, Termux aman, tanpa Rust).

    from core.providers import ProviderError, estimate_cost, resolve_provider
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Error provider-agnostik (adapter raise, llm_client mapping ke LLMError) ──

class ProviderError(Exception):
    """Base error provider (pesan sudah user-friendly)."""


class ProviderAuthError(ProviderError):
    """401/403 — key ditolak."""


class ProviderNotFoundError(ProviderError):
    """404 — model/endpoint tidak ada."""


class ProviderRateLimitError(ProviderError):
    """429 — dibatasi, boleh retry."""


class ProviderConnectionError(ProviderError):
    """Network/timeout — boleh retry."""


@dataclass
class ProviderSpec:
    """Hasil routing: mau ngomong ke mana, sebagai model apa."""

    kind: str  # "openai" | "anthropic"
    chat_url: str  # endpoint penuh (.../chat/completions atau .../messages)
    api_key: str
    model: str  # id native provider (tanpa prefix config)
    headers: dict[str, str] = field(default_factory=dict)


def provider_id_of(config_model: str) -> str:
    """Prefix provider dari 'openai/gpt-4o' → 'openai'. Tanpa '/' → ''.

    Dipakai llm_client + /model + /key buat pilih kredensial per-provider.
    Selalu lowercase; prefix tak dikenal dikembalikan apa adanya
    (routing custom via api_base).
    """
    cur = (config_model or "").strip()
    if "/" not in cur:
        return ""
    return cur.split("/", 1)[0].lower().strip()


def resolve_provider(config_model: str, api_base: str | None = None) -> ProviderSpec:
    """Routing 'anthropic/claude-x' → adapter + URL + model native.

    Tak dikenal → OpenAI-compatible dengan api_base wajib (error jelas),
    JANGAN diam-diam ke URL ngawur.
    """
    cur = (config_model or "").strip()
    low = cur.lower()
    prov, _, name = low.partition("/")
    if not name:  # tanpa prefix ("gpt-4o") → tebak dari nama
        prov, name = "", low

    if prov == "anthropic" or name.startswith("claude-"):
        base = (api_base or "https://api.anthropic.com").rstrip("/")
        return ProviderSpec(
            kind="anthropic", chat_url=base + "/v1/messages",
            api_key="", model=name or cur,
            headers={"anthropic-version": "2023-06-01"},
        )
    if prov == "gemini" or name.startswith("gemini-"):
        return ProviderSpec(
            kind="openai",
            chat_url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            api_key="", model=name or cur, headers={},
        )
    if prov == "groq":
        return ProviderSpec(
            kind="openai", chat_url="https://api.groq.com/openai/v1/chat/completions",
            api_key="", model=name or cur, headers={},
        )
    if prov == "deepseek" or name.startswith("deepseek-"):
        return ProviderSpec(
            kind="openai", chat_url="https://api.deepseek.com/chat/completions",
            api_key="", model=name or cur, headers={},
        )
    if prov == "ollama":
        base = (api_base or "http://localhost:11434").rstrip("/")
        return ProviderSpec(
            kind="openai", chat_url=base + "/v1/chat/completions",
            api_key="", model=name or cur, headers={},
        )
    if prov == "openai" or name.startswith(("gpt-", "o1", "o3", "chatgpt-")):
        return ProviderSpec(
            kind="openai", chat_url="https://api.openai.com/v1/chat/completions",
            api_key="", model=name or cur, headers={},
        )
    if prov == "custom" or api_base:
        base = (api_base or "").rstrip("/")
        if not base:
            raise ProviderError(
                "Provider custom butuh `api_base` di config "
                "(endpoint OpenAI-compatible, mis. https://host:8000/v1).")
        return ProviderSpec(
            kind="openai", chat_url=base + "/chat/completions",
            api_key="", model=name or cur, headers={},
        )
    raise ProviderError(
        f"Model `{cur}` tidak dikenali. Format: provider/nama "
        "(cth: openai/gpt-4o, anthropic/claude-sonnet-4-6, ollama/llama3.2).")


# ── Harga per 1M token (USD, ESTIMASI — cek berkala, provider suka ubah) ──
# Dipakai estimate_cost ala OpenCode (hitung lokal, tanpa server).
# Format: (substring_model, harga_input, harga_output). Urutan = prioritas.
PRICES: tuple[tuple[str, float, float], ...] = (
    ("opus", 15.0, 75.0),
    ("sonnet", 3.0, 15.0),
    ("haiku", 0.8, 4.0),
    ("gpt-4o-mini", 0.15, 0.6),
    ("gpt-4o", 2.5, 10.0),
    ("o3", 2.0, 8.0),
    ("o1", 15.0, 60.0),
    ("gemini-2.5-pro", 1.25, 10.0),
    ("gemini-2.0-flash", 0.1, 0.4),
    ("gemini", 0.5, 1.5),
    ("llama-3.3-70b", 0.59, 0.79),
    ("llama-3.1-8b", 0.05, 0.08),
    ("llama", 0.2, 0.2),
    ("qwen", 0.2, 0.2),
    ("deepseek", 0.55, 2.19),
)


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Cost USD (est). Lokal/tak dikenal → 0.0 (jujur: bukan asal)."""
    low = (model or "").lower()
    if "ollama" in low or "localhost" in low or "local" in low:
        return 0.0  # jalan di mesin sendiri = gratis
    for sub, pin, pout in PRICES:
        if sub in low:
            return (prompt_tokens * pin + completion_tokens * pout) / 1_000_000
    return 0.0
