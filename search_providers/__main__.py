"""Self-test factory search provider (python -m search_providers)."""

from types import SimpleNamespace

from core.config import Config, ConfigError
from search_providers import KNOWN_PROVIDERS, get_provider
from search_providers.base import SearchProvider
from search_providers.tavily import TavilyProvider

# Semua provider terdaftar + terinstansiasi
for _name in KNOWN_PROVIDERS:
    _p = get_provider(Config(model="m", api_key="k",
                             search_provider=_name, search_api_key="dummy"))
    assert isinstance(_p, SearchProvider), _name

# DuckDuckGo jalan tanpa key
assert isinstance(
    get_provider(Config(model="m", api_key="k",
                        search_provider="duckduckgo")), SearchProvider)

# Case-insensitive + strip
_p = get_provider(Config(model="m", api_key="k",
                         search_provider="  Tavily ", search_api_key="x"))
assert isinstance(_p, TavilyProvider), type(_p)

# Provider asing → ditolak saat konstruksi Config (ConfigError),
# dengan pesan field yang jelas. Factory tetap punya ConfigError sebagai
# pertahanan lapis dua (dicapai via config duck-typed).
try:
    Config(model="m", api_key="k", search_provider="google")
    raise AssertionError("harus ConfigError")
except ConfigError as e:
    assert "search_provider" in str(e), e

try:
    get_provider(SimpleNamespace(search_provider="google", search_api_key="x"))
    raise AssertionError("harus ConfigError")
except ConfigError as e:
    assert "tavily" in str(e).lower(), e

print(f"✅ search factory self-test OK ({len(KNOWN_PROVIDERS)} provider)")
