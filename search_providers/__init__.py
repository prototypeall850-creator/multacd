"""Factory — pilih provider search dari config.

    from search_providers import get_provider
    provider = get_provider(config)  # config.search_provider + search_api_key
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import ConfigError
from search_providers.base import SearchProvider
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
