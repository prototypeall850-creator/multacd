"""Factory — pilih provider search dari config.

    from search_providers import get_provider
    provider = get_provider(config)  # config.search_provider + search_api_key
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import ConfigError
from search_providers.base import SearchProvider, SearchResult
from search_providers.brave import BraveProvider
from search_providers.duckduckgo import DuckDuckGoProvider
from search_providers.exa import ExaProvider
from search_providers.serpapi import SerpAPIProvider
from search_providers.tavily import TavilyProvider

if TYPE_CHECKING:
    from core.config import Config

_PROVIDER_MAP: dict[str, type[SearchProvider]] = {
    "tavily": TavilyProvider,
    "exa": ExaProvider,
    "brave": BraveProvider,
    "serpapi": SerpAPIProvider,
    "duckduckgo": DuckDuckGoProvider,
}

KNOWN_PROVIDERS = tuple(_PROVIDER_MAP)


def get_provider(config: Config) -> SearchProvider:
    """Return instance provider sesuai config. Raise ConfigError kalau asing."""
    name = (config.search_provider or "").lower().strip()
    cls = _PROVIDER_MAP.get(name)
    if cls is None:
        raise ConfigError(
            f"Provider tidak dikenal: {config.search_provider!r}. "
            f"Pilihan: {', '.join(KNOWN_PROVIDERS)}.")
    return cls(api_key=config.search_api_key or "")


# Error yang TIDAK boleh di-fallback (konfigurasi salah — user harus betulkan,
# bukan disembunyikan di balik DuckDuckGo): key kosong/salah, auth, asing.
NO_FALLBACK_MARKERS = ("search_api_key", "api_key", "ditolak", "401", "403",
                       "tidak dikenal", "tidak valid")


def search_with_fallback(config: Config, query: str,
                         num_results: int = 5,
                         ) -> tuple[list[SearchResult], str, str]:
    """Cari via provider config; fallback DuckDuckGo kalau operasional gagal.

    Provider native semua (tanpa SDK) — fallback untuk gangguan operasional
    (rate limit, timeout, 5xx). Salah konfigurasi (key kosong/salah, auth,
    provider asing) tetap error jelas, tidak disembunyikan. Issue #30.

    Return (results, used_provider, notice). notice "" kalau langsung.
    Fallback ikut gagal → error asli di-raise.
    """
    provider = get_provider(config)  # lookup global → mock-able di test
    name = (getattr(config, "search_provider", "") or "").lower().strip()
    try:
        return provider.search(query, num_results=num_results), name, ""
    except Exception as first:
        # `first` dihapus Python di akhir blok except — salin dulu.
        err = first
        if any(m in str(err) for m in NO_FALLBACK_MARKERS):
            raise
    try:
        results = DuckDuckGoProvider(api_key="").search(
            query, num_results=num_results)
    except Exception:
        raise err from None
    notice = (f"`{name}` lagi gangguan ({type(err).__name__}) — "
              "hasil di bawah dari DuckDuckGo gratis.")
    return results, "duckduckgo", notice
