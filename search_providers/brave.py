"""Brave Search provider — via httpx langsung (tanpa SDK).

Response berisi snippet saja → scraped=False, konten penuh menyusul
via web_scrape (Step 2).

Butuh search_api_key "BSA-xxxx".
"""

from __future__ import annotations

from typing import Any

import httpx

from search_providers.base import SearchProvider, SearchProviderError, SearchResult

_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def _parse_response(data: dict[str, Any]) -> list[SearchResult]:
    """Parse response Brave API. Score menurun by urutan (API tidak kasih skor)."""
    out: list[SearchResult] = []
    web = data.get("web", {}) or {}
    items = web.get("results", []) or []
    for i, item in enumerate(items):
        url = item.get("url", "")
        if not url:
            continue
        out.append(SearchResult(
            title=item.get("title", "") or "",
            url=url,
            snippet=item.get("description", "") or "",
            score=max(0.0, 1.0 - i * 0.05),
            published_date=item.get("page_age", "") or "",
        ))
    return out


class BraveProvider(SearchProvider):
    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        if not self._api_key:
            raise SearchProviderError(
                "Brave butuh search_api_key. Isi `search_api_key` di "
                "~/.multacd/config.yaml (key BSA-xxxx).")
        try:
            resp = httpx.get(
                _ENDPOINT,
                params={"q": query, "count": min(num_results, 20)},
                headers={"X-Subscription-Token": self._api_key,
                         "User-Agent": "multacd/1.0 (+agentic-tui)"},
                timeout=20, follow_redirects=True,
            )
            if resp.status_code == 429:
                raise SearchProviderError(
                    "Rate limit dari Brave. Tunggu beberapa saat lalu coba lagi.")
            resp.raise_for_status()
            data = resp.json()
        except SearchProviderError:
            raise
        except httpx.TimeoutException as e:
            raise SearchProviderError(f"Brave timeout: {e}") from e
        except httpx.HTTPError as e:
            raise SearchProviderError(f"Brave HTTP error: {e}") from e
        return _parse_response(data)[:num_results]


if __name__ == "__main__":
    sample = {"web": {"results": [
        {"title": "A", "url": "https://a.com/1", "description": "snip A"},
        {"title": "B", "url": "https://b.com/2", "description": "snip B"},
        {"title": "X", "url": "", "description": "skip"},
    ]}}
    out = _parse_response(sample)
    assert len(out) == 2, out
    assert out[0].snippet == "snip A" and not out[0].scraped
    assert out[0].score > out[1].score  # menurun by urutan

    try:
        BraveProvider(api_key="").search("x")
        raise AssertionError("harus SearchProviderError")
    except SearchProviderError as e:
        assert "search_api_key" in str(e), e

    print("✅ brave self-test OK (parse + key check)")
