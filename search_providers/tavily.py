"""Tavily provider — search engine yang dirancang buat AI agent.

Native httpx (tanpa SDK): REST POST api.tavily.com/search. Murni wheel,
jalan di Termux — tidak perlu extra apa pun, cukup search_api_key.

Keunggulan: response sudah include konten penuh → tidak perlu scrape lagi.
Set content langsung dari response, scraped=True.
"""

from __future__ import annotations

from typing import Any

import httpx

from search_providers.base import SearchProvider, SearchProviderError, SearchResult

_ENDPOINT = "https://api.tavily.com/search"
_TIMEOUT = 30.0


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
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(_ENDPOINT, json={
                    "api_key": self._api_key,
                    "query": query,
                    "max_results": max(1, min(num_results, 20)),
                    "include_answer": False,
                })
        except httpx.TimeoutException as e:
            raise SearchProviderError(f"Tavily timeout: {e}") from e
        except httpx.HTTPError as e:
            raise SearchProviderError(f"Tavily koneksi gagal: {e}") from e
        if resp.status_code in (401, 403):
            raise SearchProviderError(
                "Tavily menolak search_api_key (401/403). Cek key tvly-xxxx.")
        if resp.status_code == 429:
            raise SearchProviderError(
                "Rate limit dari Tavily. Tunggu beberapa saat lalu coba lagi.")
        try:
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise SearchProviderError(f"Tavily response rusak: {e}") from e
        if not isinstance(data, dict):
            raise SearchProviderError("Tavily response bukan object JSON.")
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
