"""Tavily provider — search engine yang dirancang buat AI agent.

Keunggulan: response sudah include konten penuh → tidak perlu scrape lagi.
Set content langsung dari response, scraped=True.

Butuh: pip install "multacd[tavily]" + search_api_key "tvly-xxxx".
"""

from __future__ import annotations

from typing import Any

from search_providers.base import SearchProvider, SearchProviderError, SearchResult


def _parse_response(data: dict[str, Any]) -> list[SearchResult]:
    """Parse response Tavily API → list SearchResult. Pure function."""
    out: list[SearchResult] = []
    for item in data.get("results", []) or []:
        url = item.get("url", "")
        if not url:
            continue
        out.append(SearchResult(
            title=item.get("title", "") or "",
            url=url,
            snippet=item.get("content", "")[:500] or "",
            score=float(item.get("score", 0.0) or 0.0),
            published_date=item.get("published_date", "") or "",
            content=item.get("content", "") or "",
            scraped=True,
        ))
    return out


class TavilyProvider(SearchProvider):
    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        if not self._api_key:
            raise SearchProviderError(
                "Tavily butuh search_api_key. Isi `search_api_key` di "
                "~/.multacd/config.yaml (key tvly-xxxx).")
        try:
            from tavily import TavilyClient
        except ImportError as e:
            raise SearchProviderError(
                "SDK tavily-python belum install. Jalankan: pip install \"multacd[tavily]\""
            ) from e
        try:
            client = TavilyClient(api_key=self._api_key)
            data = client.search(query, max_results=num_results,
                                 include_answer=False)
        except Exception as e:
            raise SearchProviderError(f"Tavily search gagal: {e}") from e
        return _parse_response(data)[:num_results]


if __name__ == "__main__":
    # Parse tanpa network
    sample = {"results": [
        {"title": "A", "url": "https://a.com/1", "content": "isi penuh A",
         "score": 0.9, "published_date": "2025-01-01"},
        {"title": "B", "url": "", "content": "tanpa url → skip"},
        {"title": "C", "url": "https://c.com/3", "content": "isi C", "score": 0.5},
    ]}
    out = _parse_response(sample)
    assert len(out) == 2, out
    assert out[0].content == "isi penuh A" and out[0].scraped
    assert out[0].published_date == "2025-01-01"

    # Tanpa key → error jelas (bukan crash misterius)
    try:
        TavilyProvider(api_key="").search("x")
        raise AssertionError("harus SearchProviderError")
    except SearchProviderError as e:
        assert "search_api_key" in str(e), e

    print("✅ tavily self-test OK (parse + key check)")
