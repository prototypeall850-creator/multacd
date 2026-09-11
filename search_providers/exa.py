"""Exa provider — neural search engine buat AI agent.

Request dengan contents=True → konten langsung tersedia (mirip Tavily),
set scraped=True.

Butuh: pip install exa-py + search_api_key "exa-xxxx".
"""

from __future__ import annotations

from typing import Any

from search_providers.base import SearchProvider, SearchProviderError, SearchResult


def _parse_results(items: list[Any]) -> list[SearchResult]:
    """Parse hasil Exa (dict atau object) → SearchResult. Pure function."""
    out: list[SearchResult] = []
    for item in items or []:
        if isinstance(item, dict):
            url = item.get("url", "")
            title = item.get("title", "") or ""
            text = item.get("text", "") or ""
            date = item.get("published_date", "") or ""
            score = float(item.get("score", 0.0) or 0.0)
        else:
            url = getattr(item, "url", "")
            title = getattr(item, "title", "") or ""
            text = getattr(item, "text", "") or ""
            date = getattr(item, "published_date", "") or ""
            try:
                score = float(getattr(item, "score", 0.0) or 0.0)
            except (TypeError, ValueError):
                score = 0.0
        if not url:
            continue
        out.append(SearchResult(
            title=title, url=url, snippet=text[:500],
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
            from exa_py import Exa
        except ImportError as e:
            raise SearchProviderError(
                'SDK exa-py belum install. Jalankan: pip install "multacd[exa]"'
            ) from e
        try:
            client = Exa(api_key=self._api_key)
            # search_and_contents kalau tersedia, fallback ke search biasa.
            if hasattr(client, "search_and_contents"):
                resp = client.search_and_contents(
                    query, num_results=num_results, text=True)
            else:
                resp = client.search(query, num_results=num_results)
            items = resp.results if hasattr(resp, "results") else resp
        except Exception as e:
            raise SearchProviderError(f"Exa search gagal: {e}") from e
        return _parse_results(list(items))[:num_results]


if __name__ == "__main__":
    sample = [
        {"title": "A", "url": "https://a.com/1", "text": "konten A",
         "score": 0.8, "published_date": "2024-12-01"},
        {"title": "X", "url": "", "text": "skip"},
    ]
    out = _parse_results(sample)
    assert len(out) == 1 and out[0].scraped and out[0].content == "konten A"

    class Obj:
        url = "https://o.com/1"
        title = "O"
        text = "konten O"
        published_date = ""
        score = 0.3

    out2 = _parse_results([Obj()])
    assert len(out2) == 1 and out2[0].title == "O"

    try:
        ExaProvider(api_key="").search("x")
        raise AssertionError("harus SearchProviderError")
    except SearchProviderError as e:
        assert "search_api_key" in str(e), e

    print("✅ exa self-test OK (parse dict+obj + key check)")
