"""Search provider abstraction — satu interface untuk semua engine.

Agent tidak perlu tahu provider apa yang dipakai. Ganti provider =
ganti 2 baris di config, tidak ada perubahan kode lain.

    from search_providers import get_provider

    provider = get_provider(config)
    results = provider.search("python async programming", num_results=5)

Test cepat:
    python -m search_providers.base
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass


class SearchProviderError(Exception):
    """Error provider yang friendly — pesannya bisa langsung ke user."""


@dataclass
class SearchResult:
    """Satu hasil search. `content` diisi setelah scraping (atau langsung
    oleh provider seperti Tavily/Exa yang return konten sekalian)."""

    title: str
    url: str
    snippet: str = ""
    score: float = 0.0
    published_date: str = ""
    content: str = ""
    scraped: bool = False
    scrape_failed: bool = False

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "score": self.score,
            "published_date": self.published_date,
            "content": self.content,
            "scraped": self.scraped,
            "scrape_failed": self.scrape_failed,
        }


def _normalize_url(url: str) -> str:
    """Normalisasi ringan buat dedup: buang fragment + trailing slash."""
    return url.split("#", 1)[0].rstrip("/").lower()


class SearchProvider:
    """Abstract provider. Subclass cukup implement `search()` satu query —
    `search_many()` (parallel + dedup + sort) sudah ditangani di sini."""

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        raise NotImplementedError

    def search_many(
        self, queries: list[str], num_results_per_query: int = 5
    ) -> list[SearchResult]:
        """Jalankan semua query parallel, dedup by URL, sort by score."""
        if not queries:
            return []
        collected: list[SearchResult] = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(queries), 8)
        ) as pool:
            futs = {
                pool.submit(self.search, q, num_results_per_query): q
                for q in queries
            }
            for fut in concurrent.futures.as_completed(futs):
                try:
                    collected.extend(fut.result())
                except SearchProviderError:
                    # Satu query gagal → lanjut dengan hasil query lain.
                    continue
        # Dedup: keep kemunculan pertama (score tertinggi biasanya duluan
        # karena tiap provider return urut relevansi).
        seen: set[str] = set()
        unique: list[SearchResult] = []
        for r in collected:
            key = _normalize_url(r.url)
            if key and key not in seen:
                seen.add(key)
                unique.append(r)
        unique.sort(key=lambda r: r.score, reverse=True)
        return unique


if __name__ == "__main__":
    # 1. SearchResult defaults
    r = SearchResult(title="t", url="https://x.com/a")
    assert r.snippet == "" and r.score == 0.0 and not r.scraped
    assert r.to_dict()["url"] == "https://x.com/a"

    # 2. search_many: parallel + dedup + sort via FakeProvider
    class FakeProvider(SearchProvider):
        def search(self, query, num_results=5):
            if query == "gagal":
                raise SearchProviderError("boom")
            base = abs(hash(query)) % 100 / 100
            return [
                SearchResult(title=f"{query}-1", url="https://sama.com/x",
                             snippet="dup", score=base),
                SearchResult(title=f"{query}-2",
                             url=f"https://beda.com/{query}",
                             snippet="unik", score=base + 0.5),
            ]

    p = FakeProvider()
    out = p.search_many(["q1", "q2", "gagal"], 5)
    # dup https://sama.com/x muncul 1x; query gagal di-skip
    urls = [x.url for x in out]
    assert urls.count("https://sama.com/x") == 1, urls
    assert len(out) == 3, out  # 1 dup + 2 unik
    scores = [x.score for x in out]
    assert scores == sorted(scores, reverse=True), scores

    # 3. Query kosong → list kosong, base search raise NotImplementedError
    assert p.search_many([]) == []
    try:
        SearchProvider().search("x")
        raise AssertionError("harus NotImplementedError")
    except NotImplementedError:
        pass

    # 4. Normalisasi URL buat dedup
    assert _normalize_url("https://A.com/X/#frag") == _normalize_url("https://a.com/x")

    print("✅ search base self-test OK (dedup + sort + fallback)")
