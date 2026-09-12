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


SDK_MISSING_MARKER = "belum install"


def search_with_fallback(config: Config, query: str,
                         num_results: int = 5,
                         ) -> tuple[list[SearchResult], str, str]:
    """Cari via provider config; fallback DuckDuckGo kalau SDK-nya hilang.

    Tavily/Exa jadi extra opsional (rantai Rust tanpa wheel Android —
    di Termux mustahil install). Tanpa fallback, riset mati total di HP.
    Issue #30.

    Return (results, used_provider, notice). notice "" kalau langsung.
    Error non-SDK (key salah, network, provider asing) di-raise apa adanya
    — jangan disembunyikan. Fallback ikut gagal → error asli di-raise.
    """
    provider = get_provider(config)  # lookup global → mock-able di test
    name = (getattr(config, "search_provider", "") or "").lower().strip()
    try:
        return provider.search(query, num_results=num_results), name, ""
    except Exception as first:
        if SDK_MISSING_MARKER not in str(first):
            raise
        sdk_err = first
    try:
        results = DuckDuckGoProvider(api_key="").search(
            query, num_results=num_results)
    except Exception:
        raise sdk_err from None
    notice = (f"`{name}` tak bisa dipakai di sini (SDK belum install) — "
              "hasil di bawah dari DuckDuckGo gratis.")
    return results, "duckduckgo", notice
