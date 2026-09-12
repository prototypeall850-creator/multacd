"""Unit: search_with_fallback — SDK hilang → DuckDuckGo (tanpa network).

Semua provider dimock (module attr), tidak ada network/LLM/config asli.
Issue #30.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import search_providers
from search_providers import search_with_fallback
from search_providers.base import SearchProviderError, SearchResult


def _res(url: str) -> SearchResult:
    return SearchResult(title="T", url=url, snippet="s", score=0.5)


def _cfg(name: str, key: str = "k") -> SimpleNamespace:
    return SimpleNamespace(search_provider=name, search_api_key=key)


def test_direct_no_fallback(monkeypatch):
    """Provider sehat → hasil langsung, notice kosong."""
    class _P:
        def search(self, q, num_results=5):
            return [_res("https://a.com")]
    monkeypatch.setattr(search_providers, "get_provider", lambda cfg: _P())
    out, used, notice = search_with_fallback(_cfg("brave"), "x", 3)
    assert [r.url for r in out] == ["https://a.com"]
    assert used == "brave" and notice == ""


def test_sdk_missing_falls_back(monkeypatch):
    """Tavily gangguan operasional (rate limit/timeout) → DDG + notice."""
    def _boom(cfg):
        class _P:
            def search(self, q, num_results=5):
                raise SearchProviderError("Rate limit dari Tavily")
        return _P()
    monkeypatch.setattr(search_providers, "get_provider", _boom)
    monkeypatch.setattr(
        search_providers, "DuckDuckGoProvider",
        lambda api_key="": type("D", (), {
            "search": lambda self, q, num_results=5: [_res("https://d.com")]})())
    out, used, notice = search_with_fallback(_cfg("tavily"), "x", 3)
    assert [r.url for r in out] == ["https://d.com"]
    assert used == "duckduckgo" and "tavily" in notice and "DuckDuckGo" in notice


def test_key_error_no_fallback(monkeypatch):
    """Key kosong/salah → fail jelas, JANGAN fallback (jangan sembunyikan)."""
    def _bad(cfg):
        class _P:
            def search(self, q, num_results=5):
                raise SearchProviderError("Tavily butuh search_api_key")
        return _P()
    monkeypatch.setattr(search_providers, "get_provider", _bad)
    with pytest.raises(SearchProviderError, match="search_api_key"):
        search_with_fallback(_cfg("tavily"), "x", 1)


def test_fallback_fails_reraises_original(monkeypatch):
    """DDG ikut gagal → error asli (operasional), bukan error DDG."""
    def _boom(cfg):
        class _P:
            def search(self, q, num_results=5):
                raise SearchProviderError("Exa timeout: tempo habis")
        return _P()
    monkeypatch.setattr(search_providers, "get_provider", _boom)
    def _ddg_boom(api_key=""):
        class _D:
            def search(self, q, num_results=5):
                raise SearchProviderError("DDG timeout")
        return _D()
    monkeypatch.setattr(search_providers, "DuckDuckGoProvider", _ddg_boom)
    with pytest.raises(SearchProviderError, match="tempo habis"):
        search_with_fallback(_cfg("exa"), "x", 1)
