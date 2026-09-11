"""Unit: Tavily parse + error tanpa key (tanpa network)."""

from __future__ import annotations

import pytest

from search_providers.base import SearchProviderError
from search_providers.tavily import TavilyProvider
from search_providers.tavily import _parse_response as parse


def test_parse_skips_empty_url():
    data = {"results": [
        {"title": "A", "url": "https://a.test", "content": "isi",
         "score": 0.9},
        {"title": "kosong", "url": "", "content": "x"},
    ]}
    out = parse(data)
    assert len(out) == 1
    assert out[0].url == "https://a.test" and out[0].scraped


def test_no_key_raises_helpful():
    with pytest.raises(SearchProviderError, match="search_api_key"):
        TavilyProvider(api_key="").search("ai")
