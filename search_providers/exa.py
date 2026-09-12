"""Exa provider — neural search engine buat AI agent.

Native httpx (tanpa SDK): REST POST api.exa.ai/search dengan contents.text.
Murni wheel, jalan di Termux — cukup search_api_key "exa-xxxx".

Konten langsung tersedia (mirip Tavily), set scraped=True.
"""

from __future__ import annotations

from typing import Any

import httpx

from search_providers.base import SearchProvider, SearchProviderError, SearchResult

_ENDPOINT = "https://api.exa.ai/search"
_TIMEOUT = 30.0


def _parse_results(items: list[Any]) -> list[SearchResult]:
    """Parse hasil Exa REST (dict) → SearchResult. Pure function."""
    out: list[SearchResult] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        url = item.get("url", "")
        if not url:
            continue
        text = item.get("text", "") or ""
        date = (item.get("publishedDate", "")
                or item.get("published_date", "") or "")
        try:
            score = float(item.get("score", 0.0) or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        out.append(SearchResult(
            title=item.get("title", "") or "", url=url, snippet=text[:500],
            score=score, published_date=date,
            content=text, scraped=True,
        ))
    return out


class ExaProvider(SearchProvider):
    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        if not self._api_key:
            raise SearchProviderError(
                "Exa butuh search_api_key. Isi `search_api_key` di "
                "~/.multacd/config.yaml (key exa-xxxx).")
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(
                    _ENDPOINT,
                    headers={"x-api-key": self._api_key,
                             "Content-Type": "application/json"},
                    json={"query": query,
                          "numResults": max(1, min(num_results, 20)),
                          "contents": {"text": True}},
                )
        except httpx.TimeoutException as e:
            raise SearchProviderError(f"Exa timeout: {e}") from e
        except httpx.HTTPError as e:
            raise SearchProviderError(f"Exa koneksi gagal: {e}") from e
        if resp.status_code in (401, 403):
            raise SearchProviderError(
                "Exa menolak search_api_key (401/403). Cek key exa-xxxx.")
        if resp.status_code == 429:
            raise SearchProviderError(
                "Rate limit dari Exa. Tunggu beberapa saat lalu coba lagi.")
        try:
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise SearchProviderError(f"Exa response rusak: {e}") from e
        if not isinstance(data, dict):
            raise SearchProviderError("Exa response bukan object JSON.")
        return _parse_results(data.get("results", []) or [])[:num_results]


if __name__ == "__main__":
    sample = [
        {"title": "A", "url": "https://a.com/1", "text": "konten A",
         "score": 0.8, "publishedDate": "2024-12-01"},
        {"title": "X", "url": "", "text": "skip"},
        {"title": "B", "url": "https://b.com/2", "text": "konten B",
         "score": "jelek", "published_date": "2024-01-01"},
    ]
    out = _parse_results(sample)
    assert len(out) == 2 and out[0].scraped and out[0].content == "konten A"
    assert out[0].published_date == "2024-12-01"
    assert out[1].score == 0.0  # skor ngawur → 0.0, bukan crash

    try:
        ExaProvider(api_key="").search("x")
        raise AssertionError("harus SearchProviderError")
    except SearchProviderError as e:
        assert "search_api_key" in str(e), e

    print("✅ exa self-test OK (parse REST + key check)")
