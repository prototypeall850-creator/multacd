"""SerpAPI provider — via httpx langsung (tanpa SDK).

Response berisi snippet → scraped=False, konten penuh via web_scrape.

Butuh search_api_key SerpAPI.
"""

from __future__ import annotations

from typing import Any

import httpx

from search_providers.base import SearchProvider, SearchProviderError, SearchResult

_ENDPOINT = "https://serpapi.com/search"


def _parse_response(data: dict[str, Any]) -> list[SearchResult]:
    """Parse organic_results SerpAPI. Score menurun by urutan."""
    out: list[SearchResult] = []
    for i, item in enumerate(data.get("organic_results", []) or []):
        url = item.get("link", "")
        if not url:
            continue
        out.append(SearchResult(
            title=item.get("title", "") or "",
            url=url,
            snippet=item.get("snippet", "") or "",
            score=max(0.0, 1.0 - i * 0.05),
            published_date=item.get("date", "") or "",
        ))
    return out


class SerpAPIProvider(SearchProvider):
    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        if not self._api_key:
            raise SearchProviderError(
                "SerpAPI butuh search_api_key. Isi `search_api_key` di "
                "~/.multacd/config.yaml.")
        try:
            resp = httpx.get(
                _ENDPOINT,
                params={"api_key": self._api_key, "q": query,
                        "num": min(num_results, 20), "engine": "google"},
                headers={"User-Agent": "multacd/1.0 (+agentic-tui)"},
                timeout=20, follow_redirects=True,
            )
            if resp.status_code in (429, 403):
                raise SearchProviderError(
                    "Rate limit dari SerpAPI. Tunggu beberapa saat lalu coba lagi.")
            resp.raise_for_status()
            data = resp.json()
        except SearchProviderError:
            raise
        except httpx.TimeoutException as e:
            raise SearchProviderError(f"SerpAPI timeout: {e}") from e
        except httpx.HTTPError as e:
            raise SearchProviderError(f"SerpAPI HTTP error: {e}") from e
        if data.get("error"):
            raise SearchProviderError(f"SerpAPI error: {data['error']}")
        return _parse_response(data)[:num_results]


if __name__ == "__main__":
    sample = {"organic_results": [
        {"title": "A", "link": "https://a.com/1", "snippet": "snip A"},
        {"title": "B", "link": "https://b.com/2", "snippet": "snip B",
         "date": "Jan 2025"},
    ]}
    out = _parse_response(sample)
    assert len(out) == 2 and out[1].published_date == "Jan 2025"
    assert not out[0].scraped and out[0].score > out[1].score

    try:
        SerpAPIProvider(api_key="").search("x")
        raise AssertionError("harus SearchProviderError")
    except SearchProviderError as e:
        assert "search_api_key" in str(e), e

    print("✅ serpapi self-test OK (parse + key check)")
