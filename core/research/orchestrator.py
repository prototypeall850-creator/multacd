"""Research orchestrator — quick & deep research flow (Step 5-6).

quick_research(topic):
  queries (LLM) → search parallel → dedup top-N → scrape parallel
  → synthesis (LLM) → QuickResult(answer, sources, queries)

Sengaja async + injectable (llm, search_fn, scrape_fn, on_event) supaya
gampang di-test tanpa network dan gampang disambung ke TUI (Step 8)
via callback on_event. Tool wrapper sync ada di tools/research/.

Event yang di-emit (dict):
  queries      {queries}                    — query selesai di-generate
  sources      {sources: [{url,title,status}]} — daftar sumber ditemukan
  source       {url, status}                — status satu sumber berubah
  synthesizing {}                           — mulai synthesis
  answer       {answer}                     — jawaban final

status: searching | scraped | snippet | failed
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from core.research.query_generator import generate_quick_queries
from search_providers.base import SearchResult

MAX_SOURCE_CHARS = 8000  # cap per sumber sebelum masuk LLM (lihat issue #6)


@dataclass
class QuickResult:
    answer: str = ""
    sources: list[SearchResult] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"answer": self.answer,
                "sources": [s.to_dict() for s in self.sources],
                "queries": self.queries}


def _norm(url: str) -> str:
    return url.split("#", 1)[0].rstrip("/").lower()


def _default_search_fn(config: Any) -> Callable:
    from search_providers import get_provider

    provider = get_provider(config)

    def _search(query: str, num: int) -> list[SearchResult]:
        return provider.search(query, num_results=num)

    return _search


def _default_scrape_fn(config: Any) -> Callable:
    from tools.research.web_scrape import web_scrape

    timeout = getattr(config, "research_scrape_timeout", 15)

    def _scrape(url: str, snippet: str = "") -> tuple[str, str]:
        """Return (content, content_source)."""
        r = web_scrape(url, timeout=timeout, snippet=snippet)
        if not r["success"]:
            return "", "failed"
        res = r["result"]
        return res.get("content", ""), res.get("content_source", "failed")

    return _scrape


def _default_llm(config: Any) -> Any:
    from core.config import load_config
    from core.llm_client import setup_client
    return setup_client(config or load_config())


async def quick_research(
    topic: str,
    config: Any = None,
    llm: Any = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    search_fn: Callable | None = None,
    scrape_fn: Callable | None = None,
    language: str = "",
) -> QuickResult:
    """Riset cepat 1 round (~15-30 detik). Selalu return, tidak pernah raise."""
    def _emit(ev: dict[str, Any]) -> None:
        if on_event is not None:
            with suppress(Exception):
                on_event(ev)

    topic = (topic or "").strip()
    if not topic:
        return QuickResult(answer="Topik kosong — tidak ada yang diriset.")

    n_queries = getattr(config, "research_quick_queries", 3) or 3
    per_query = getattr(config, "search_results_per_query", 5) or 5
    max_sources = getattr(config, "research_quick_max_sources", 5) or 5
    llm = llm or _default_llm(config)
    search_fn = search_fn or _default_search_fn(config)
    scrape_fn = scrape_fn or _default_scrape_fn(config)

    # STEP 1 — generate queries (LLM error → fallback [topic], tidak raise)
    try:
        queries = await generate_quick_queries(topic, n=n_queries, llm=llm)
    except Exception:
        queries = [topic]
    _emit({"type": "queries", "queries": queries})

    # STEP 2 — search parallel, dedup, top-N
    try:
        found: list[list[SearchResult]] = await asyncio.gather(
            *[asyncio.to_thread(search_fn, q, per_query) for q in queries])
    except Exception:
        found = []
    seen: set[str] = set()
    sources: list[SearchResult] = []
    for batch in found:
        for r in batch or []:
            key = _norm(r.url)
            if key and key not in seen:
                seen.add(key)
                sources.append(r)
            if len(sources) >= max_sources:
                break
        if len(sources) >= max_sources:
            break
    sources.sort(key=lambda r: r.score, reverse=True)
    sources = sources[:max_sources]
    _emit({"type": "sources",
           "sources": [{"url": s.url, "title": s.title, "status": "searching"}
                       for s in sources]})

    if not sources:
        return QuickResult(
            answer="Tidak ada hasil untuk topik ini. Coba rephrasing pertanyaan.",
            sources=[], queries=queries)

    # STEP 3 — scrape parallel (yang sudah punya konten, mis. Tavily, skip)
    async def _scrape_one(s: SearchResult) -> None:
        if s.scraped and s.content:
            _emit({"type": "source", "url": s.url, "status": "scraped"})
            return
        try:
            content, src = await asyncio.to_thread(scrape_fn, s.url, s.snippet)
        except Exception:
            content, src = "", "failed"
        s.content = content
        s.scraped = src == "scraped"
        s.scrape_failed = src == "failed"
        _emit({"type": "source", "url": s.url, "status": src})

    await asyncio.gather(*[_scrape_one(s) for s in sources])

    # STEP 4 — synthesis
    _emit({"type": "synthesizing"})
    blocks = []
    for i, s in enumerate(sources, 1):
        body = (s.content or s.snippet or "(tidak ada konten)").strip()
        blocks.append(f"Sumber {i}: {s.title} ({s.url})\n{body[:MAX_SOURCE_CHARS]}")
    lang = language.strip() or "sama dengan pertanyaan user"
    prompt = (
        f"Berdasarkan sumber-sumber berikut, jawab pertanyaan: {topic}\n\n"
        + "\n\n".join(blocks) +
        "\n\nFormat output:\n## Jawaban\n[jawaban utama]\n"
        "## Detail\n[penjelasan lebih dalam]\n## Sumber\n"
        "[list sumber dengan URL]\nGunakan bahasa: " + lang)
    try:
        done = await llm.complete([{"role": "user", "content": prompt}])
        answer = (done.text or "").strip()
    except Exception as e:
        answer = (f"Riset terkumpul dari {len(sources)} sumber tapi synthesis "
                  f"gagal ({type(e).__name__}: {e}). "
                  "Konten sumber tetap tersedia di atas.")
    if not answer:
        answer = "(LLM tidak mengembalikan jawaban.)"
    _emit({"type": "answer", "answer": answer})
    return QuickResult(answer=answer, sources=sources, queries=queries)


if __name__ == "__main__":
    from core.llm_client import StreamDone

    class FakeLLM:
        def __init__(self, texts: list[str]):
            self.texts = list(texts)

        async def complete(self, messages):
            return StreamDone(self.texts.pop(0), [])

    def _mk_scraped(url: str, score: float) -> SearchResult:
        # Simulasi Tavily: konten langsung ada.
        return SearchResult(title=f"T {url}", url=url, snippet="sn",
                            score=score, content="KONTEN " + url, scraped=True)

    async def _run() -> None:
        events: list[dict] = []

        # 1. Full flow dengan fake (tanpa network): dedup + top-N + synthesis
        def fake_search(q: str, num: int) -> list[SearchResult]:
            return [_mk_scraped("https://sama.com/x", 0.9),
                    _mk_scraped(f"https://beda.com/{q}", 0.4)]

        def fake_scrape(url: str, snippet: str = "") -> tuple[str, str]:
            raise AssertionError("tidak boleh dipanggil (konten sudah ada)")

        llm = FakeLLM(['["q1", "q2"]', "## Jawaban\nini jawaban final"])
        res = await quick_research(
            "topik", llm=llm, search_fn=fake_search, scrape_fn=fake_scrape,
            on_event=events.append)
        urls = [s.url for s in res.sources]
        assert urls.count("https://sama.com/x") == 1, urls  # dedup
        assert res.queries == ["q1", "q2"]
        assert "jawaban final" in res.answer, res.answer
        kinds = [e["type"] for e in events]
        assert kinds[:2] == ["queries", "sources"], kinds
        assert kinds[-2:] == ["synthesizing", "answer"], kinds
        assert kinds[2:-2] == ["source"] * len(res.sources), kinds

        # 2. Scrape path (provider tanpa konten, mis. Brave)
        def bare_search(q: str, num: int) -> list[SearchResult]:
            return [SearchResult(title="B", url="https://b.com/1",
                                 snippet="snip B", score=0.7)]

        def good_scrape(url: str, snippet: str = "") -> tuple[str, str]:
            return "ISI SCRAPE " + url, "scraped"

        llm = FakeLLM(['["q"]', "## Jawaban\nok"])
        res = await quick_research("t", llm=llm, search_fn=bare_search,
                                   scrape_fn=good_scrape)
        assert res.sources[0].content == "ISI SCRAPE https://b.com/1"
        assert res.sources[0].scraped

        # 3. Scrape gagal semua → snippet dipakai, synthesis tetap jalan
        def bad_scrape(url: str, snippet: str = "") -> tuple[str, str]:
            return snippet, "snippet"

        llm = FakeLLM(['["q"]', "## Jawaban\npakai snippet"])
        res = await quick_research("t", llm=llm, search_fn=bare_search,
                                   scrape_fn=bad_scrape)
        assert "pakai snippet" in res.answer
        assert not res.sources[0].scraped

        # 4. Nol hasil → pesan rephrasing, bukan crash
        llm = FakeLLM(['["q"]', "tidak dipakai"])
        res = await quick_research("t", llm=llm,
                                   search_fn=lambda q, n: [],
                                   scrape_fn=bad_scrape)
        assert "rephrasing" in res.answer and res.sources == []

        # 5. Topik kosong → pesan jelas
        res = await quick_research("   ", llm=llm)
        assert "kosong" in res.answer

        # 6. LLM synthesis error → jawaban fallback, sumber tetap ada
        class BoomLLM(FakeLLM):
            async def complete(self, messages):
                if "Berdasarkan sumber" in messages[0]["content"]:
                    raise RuntimeError("putus")
                return StreamDone('["q"]', [])

        res = await quick_research("t", llm=BoomLLM([]),
                                   search_fn=bare_search,
                                   scrape_fn=good_scrape)
        assert "gagal" in res.answer and len(res.sources) == 1

        # 7. Cap konten per sumber (issue #6)
        big = "z" * (MAX_SOURCE_CHARS + 100)
        llm = FakeLLM(['["q"]', "## Jawaban\nok"])

        seen_prompt: list[str] = []

        class CapLLM:
            async def complete(self, messages):
                seen_prompt.append(messages[0]["content"])
                return StreamDone("## Jawaban\nok", [])

        def big_search(q: str, num: int) -> list[SearchResult]:
            return [SearchResult(title="G", url="https://g.com/1",
                                 snippet="s", score=1.0,
                                 content=big, scraped=True)]

        await quick_research("t", llm=CapLLM(), search_fn=big_search,
                             scrape_fn=bad_scrape)
        assert len(seen_prompt[0]) < len(big) + 2000, len(seen_prompt[0])
        assert big not in seen_prompt[0]

    asyncio.run(_run())
    print("✅ orchestrator quick self-test OK (7 skenario)")
