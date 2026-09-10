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

from core.research.query_generator import (
    generate_deep_queries,
    generate_followup_queries,
    generate_quick_queries,
)
from search_providers.base import SearchResult

MAX_SOURCE_CHARS = 8000  # cap per sumber sebelum masuk LLM (lihat issue #6)
MAX_ROUNDS_HARD = 10  # batas keamanan absolut (config default 5)


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
    from core.config import get_active_config, load_config
    from core.llm_client import setup_client
    # Active config sesi (Bug 3) — hormati --config & /model.
    return setup_client(config or get_active_config() or load_config())


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
           "sources": [{"url": s.url, "title": s.title, "status": "searching",
                        "preview": (s.content or s.snippet or "")[:600]}
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
        _emit({"type": "source", "url": s.url, "status": src,
               "preview": (content or s.snippet or "")[:600]})

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


@dataclass
class DeepResult:
    report: str = ""
    sources: list[SearchResult] = field(default_factory=list)
    rounds: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"report": self.report,
                "sources": [s.to_dict() for s in self.sources],
                "rounds": self.rounds}


def _parse_analysis(text: str) -> dict[str, Any]:
    """Parse JSON analisis round {findings, gaps, sufficient_coverage}.

    Gagal parse → seluruh teks jadi findings (tidak pernah deadlock).
    """
    import json as _json

    try:
        data = _json.loads(text.strip())
        if isinstance(data, dict):
            return {"findings": str(data.get("findings", "") or ""),
                    "gaps": str(data.get("gaps", "") or ""),
                    "sufficient_coverage": bool(
                        data.get("sufficient_coverage", False))}
    except (ValueError, AttributeError):
        pass
    if text.strip():
        return {"findings": text.strip(), "gaps": "",
                "sufficient_coverage": False}
    return {"findings": "(tidak ada temuan)", "gaps": "",
            "sufficient_coverage": False}


async def _analyze_round(llm: Any, topic: str, round_no: int,
                         blocks: list[str],
                         prev_findings: list[str]) -> dict[str, Any]:
    """LLM baca konten round → findings + gaps + coverage flag."""
    ctx = ""
    if prev_findings:
        ctx = ("Temuan round sebelumnya:\n" + "\n".join(prev_findings) + "\n\n")
    prompt = (
        f"Topik riset: {topic}\n{ctx}Konten round {round_no}:\n"
        + "\n\n".join(blocks) +
        "\n\nAnalisis dan return HANYA JSON: "
        '{"findings": "apa yang diketahui dari round ini", '
        '"gaps": "aspek yang masih gelap / follow-up questions", '
        '"sufficient_coverage": true/false (true kalau topik sudah tercakup '
        "penuh, tidak perlu round lagi)}")
    try:
        done = await llm.complete([{"role": "user", "content": prompt}])
        return _parse_analysis(done.text or "")
    except Exception:
        return {"findings": "(analisis gagal — lanjut dengan konten mentah)",
                "gaps": "", "sufficient_coverage": False}


async def _scrape_new(sources: list[SearchResult], scrape_fn: Callable,
                      emit: Callable) -> None:
    """Scrape sumber yang belum punya konten (parallel)."""
    async def _one(s: SearchResult) -> None:
        if s.scraped and s.content:
            emit({"type": "source", "url": s.url, "status": "scraped",
                  "preview": (s.content or "")[:600]})
            return
        try:
            content, src = await asyncio.to_thread(scrape_fn, s.url, s.snippet)
        except Exception:
            content, src = "", "failed"
        s.content = content
        s.scraped = src == "scraped"
        s.scrape_failed = src == "failed"
        emit({"type": "source", "url": s.url, "status": src,
              "preview": (content or s.snippet or "")[:600]})

    await asyncio.gather(*[_one(s) for s in sources])


async def deep_research(
    topic: str,
    max_rounds: int | None = None,
    config: Any = None,
    llm: Any = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    search_fn: Callable | None = None,
    scrape_fn: Callable | None = None,
    language: str = "",
) -> DeepResult:
    """Riset mendalam multi-round (~2-5 menit). Selalu return, tidak raise."""
    def _emit(ev: dict[str, Any]) -> None:
        if on_event is not None:
            with suppress(Exception):
                on_event(ev)

    topic = (topic or "").strip()
    if not topic:
        return DeepResult(report="Topik kosong — tidak ada yang diriset.")

    cfg_rounds = getattr(config, "research_deep_rounds", 5) or 5
    max_rounds = max(1, min(max_rounds or cfg_rounds, MAX_ROUNDS_HARD))
    per_query = getattr(config, "search_results_per_query", 5) or 5
    q_per_round = getattr(config, "research_deep_queries_per_round", 4) or 4
    max_sources = getattr(config, "research_deep_max_sources", 20) or 20
    llm = llm or _default_llm(config)
    search_fn = search_fn or _default_search_fn(config)
    scrape_fn = scrape_fn or _default_scrape_fn(config)
    lang = (language or "").strip() or "sama dengan pertanyaan user"

    all_sources: list[SearchResult] = []
    seen: set[str] = set()
    all_findings: list[str] = []
    rounds: list[dict[str, Any]] = []
    stop_reason = ""

    for rnd in range(1, max_rounds + 1):
        _emit({"type": "round_start", "round": rnd, "total": max_rounds})
        # 1. Queries: broad (round 1) / followup (round 2+)
        try:
            if rnd == 1:
                queries = await generate_deep_queries(
                    topic, n=q_per_round, llm=llm)
            else:
                queries = await generate_followup_queries(
                    topic, "\n".join(all_findings),
                    rounds[-1].get("gaps", ""), n=q_per_round, llm=llm)
        except Exception:
            queries = [topic]
        _emit({"type": "queries", "round": rnd, "queries": queries})

        # 2. Search parallel, skip URL yang sudah ada
        try:
            found: list[list[SearchResult]] = await asyncio.gather(
                *[asyncio.to_thread(search_fn, q, per_query) for q in queries])
        except Exception:
            found = []
        fresh: list[SearchResult] = []
        for batch in found:
            for r in batch or []:
                key = _norm(r.url)
                if key and key not in seen:
                    seen.add(key)
                    fresh.append(r)
        fresh.sort(key=lambda r: r.score, reverse=True)
        # Hormati batas total sumber
        room = max_sources - len(all_sources)
        if room <= 0:
            stop_reason = (f"Riset dihentikan di round {rnd}/{max_rounds} karena "
                           f"batas sumber ({max_sources}) tercapai. "
                           "Melanjutkan ke synthesis...")
            _emit({"type": "limit", "reason": stop_reason})
            break
        fresh = fresh[:room]
        if not fresh:
            if rnd == 1:
                return DeepResult(
                    report="Tidak ada hasil untuk topik ini. "
                           "Coba rephrasing pertanyaan.",
                    sources=[], rounds=rounds)
            stop_reason = (f"Tidak ada sumber baru di round {rnd} — "
                           "melanjutkan ke synthesis...")
            _emit({"type": "limit", "reason": stop_reason})
            break

        # 3. Scrape + update panel
        _emit({"type": "sources", "round": rnd,
               "sources": [{"url": s.url, "title": s.title,
                            "status": "searching",
                            "preview": (s.content or s.snippet or "")[:600]}
                           for s in fresh]})
        await _scrape_new(fresh, scrape_fn, _emit)
        all_sources.extend(fresh)

        # 4. Analisis round
        blocks = []
        for i, s in enumerate(fresh, 1):
            body = (s.content or s.snippet or "(tidak ada konten)").strip()
            blocks.append(f"Sumber: {s.title} ({s.url})\n"
                          f"{body[:MAX_SOURCE_CHARS]}")
        analysis = await _analyze_round(llm, topic, rnd, blocks, all_findings)
        all_findings.append(f"Round {rnd}: {analysis['findings']}")
        rounds.append({"round": rnd, "queries": queries,
                       "source_urls": [s.url for s in fresh],
                       "findings": analysis["findings"],
                       "gaps": analysis["gaps"]})
        _emit({"type": "round", "round": rnd, "total": max_rounds,
               "findings": analysis["findings"], "gaps": analysis["gaps"],
               "sources_read": len(all_sources)})
        if analysis["sufficient_coverage"]:
            stop_reason = (f"Cakupan dinilai cukup di round {rnd}/{max_rounds} — "
                           "melanjutkan ke synthesis...")
            _emit({"type": "limit", "reason": stop_reason})
            break

    # 5. Cross-reference check: deteksi kontradiksi
    contradictions = ""
    if len(all_sources) > 1:
        cross_prompt = (
            f"Topik: {topic}\nTemuan per round:\n" + "\n".join(all_findings) +
            "\n\nPeriksa kontradiksi: apakah ada sumber yang saling "
            "bertentangan untuk hal yang sama? Return HANYA JSON: "
            '{"contradictions": "deskripsi kontradiksi + sumbernya, '
            'atau string kosong kalau tidak ada"}')
        try:
            done = await llm.complete([{"role": "user", "content": cross_prompt}])
            import json as _json

            contradictions = str(
                _json.loads((done.text or "").strip()).get(
                    "contradictions", "")) or ""
        except Exception:
            contradictions = ""

    # 6. Final synthesis
    _emit({"type": "synthesizing"})
    src_lines = []
    for rd in rounds:
        src_lines.append(f"Round {rd['round']}:")
        for u in rd["source_urls"]:
            src_lines.append(f"  - {u}")
    prompt = (
        f"Buat laporan riset mendalam tentang: {topic}\n\n"
        f"Temuan:\n" + "\n".join(all_findings) + "\n\n"
        f"Kontradiksi antar sumber: {contradictions or '(tidak ada)'}\n\n"
        "Struktur laporan:\n# {judul}\n## Ringkasan Eksekutif\n"
        "[2-3 paragraf inti]\n## Temuan Utama\n[poin per aspek]\n"
        "## Analisis Mendalam\n[detail per subtopik + referensi sumber]\n"
        "## Kontradiksi & Ketidakpastian\n"
        "[kalau tidak ada, tulis 'Tidak ditemukan kontradiksi berarti']\n"
        "## Kesimpulan\n[sintesis akhir + implikasi]\n## Sumber\n"
        + "\n".join(src_lines)
        + f"\n\nGunakan bahasa: {lang}")
    if stop_reason:
        prompt += f"\n\nCatatan: {stop_reason}"
    try:
        done = await llm.complete([{"role": "user", "content": prompt}])
        report = (done.text or "").strip() or "(LLM tidak mengembalikan laporan.)"
    except Exception as e:
        report = (f"Laporan gagal disintesis ({type(e).__name__}: {e}). "
                  f"Temuan mentah {len(rounds)} round tetap tersedia.")
    _emit({"type": "report", "report": report})
    return DeepResult(report=report, sources=all_sources, rounds=rounds)


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

        # 8. Deep: berhenti awal saat coverage cukup (round 2/5)
        import json as _json

        def deep_search(q: str, num: int) -> list[SearchResult]:
            return [_mk_scraped(f"https://deep.com/{q}", 0.8)]

        def _analysis(findings: str, gaps: str, cov: bool) -> str:
            return _json.dumps({"findings": findings, "gaps": gaps,
                                "sufficient_coverage": cov})

        llm = FakeLLM([
            '["dq1", "dq2"]',                      # round 1 queries
            _analysis("tahu A", "gelap B", False),  # round 1 analisis
            '["fq1"]',                              # round 2 followup
            _analysis("tahu B", "", True),          # round 2 → cukup
            _json.dumps({"contradictions": ""}),    # cross-ref
            "# Laporan\n## Ringkasan Eksekutif\nok",  # final
        ])
        dev: list[dict] = []
        dres = await deep_research("topik deep", max_rounds=5, llm=llm,
                                   search_fn=deep_search,
                                   scrape_fn=good_scrape, on_event=dev.append)
        assert len(dres.rounds) == 2, dres.rounds  # berhenti di round 2
        assert dres.rounds[0]["findings"] == "tahu A"
        assert dres.rounds[1]["gaps"] == ""
        assert "Laporan" in dres.report
        assert len(dres.sources) == 3, dres.sources  # 2 + 1
        kinds = [e["type"] for e in dev]
        assert "round_start" in kinds and "round" in kinds
        assert kinds[-2:] == ["synthesizing", "report"], kinds

        # 9. Deep: URL duplikat antar round di-skip
        llm = FakeLLM([
            '["q"]', _analysis("A", "masih gelap", False),
            '["q"]', _analysis("B", "", True),
            _json.dumps({"contradictions": "X bilang 1, Y bilang 2"}),
            "# Lap",
        ])
        dres = await deep_research(
            "t", max_rounds=3, llm=llm,
            search_fn=lambda q, n: [_mk_scraped("https://itu-itu.com/a", 0.9)],
            scrape_fn=good_scrape)
        # Round 2 tidak dapat sumber baru → stop, total 1 sumber
        assert len(dres.rounds) == 1 and len(dres.sources) == 1, (
            dres.rounds, dres.sources)

        # 10. Deep: batas max_total_sources memaksa berhenti
        from types import SimpleNamespace as _NS

        cfg = _NS(research_deep_rounds=5, search_results_per_query=5,
                  research_deep_queries_per_round=4,
                  research_deep_max_sources=2, research_scrape_timeout=15)
        llm = FakeLLM([
            '["q1"]', _analysis("A", "g", False),
            '["q2"]',
            _json.dumps({"contradictions": ""}),
            "# Lap",
        ])
        n = [0]

        def many_search(q: str, num: int) -> list[SearchResult]:
            n[0] += 1
            return [_mk_scraped(f"https://m.com/{q}-{n[0]}-a", 0.8),
                    _mk_scraped(f"https://m.com/{q}-{n[0]}-b", 0.7)]

        evs: list[dict] = []
        dres = await deep_research("t", config=cfg, llm=llm,
                                   search_fn=many_search,
                                   scrape_fn=good_scrape, on_event=evs.append)
        assert len(dres.sources) <= 2, dres.sources
        assert any("batas sumber" in e.get("reason", "") for e in evs), evs

        # 11. Deep: round 1 nol hasil → pesan rephrasing
        llm = FakeLLM(['["q"]'])
        dres = await deep_research("t", max_rounds=3, llm=llm,
                                   search_fn=lambda q, n: [],
                                   scrape_fn=good_scrape)
        assert "rephrasing" in dres.report and dres.rounds == []

        # 12. Deep: topik kosong + max_rounds di-clamp
        dres = await deep_research("   ", llm=llm)
        assert "kosong" in dres.report
        llm = FakeLLM(['["q"]', _analysis("A", "", True),
                        _json.dumps({"contradictions": ""}), "# Lap"])
        dres = await deep_research(
            "t", max_rounds=99, llm=llm,
            search_fn=lambda q, n: [_mk_scraped("https://c.com/1", 0.5)],
            scrape_fn=good_scrape)
        assert len(dres.rounds) == 1  # tidak infinite walau max 99

    asyncio.run(_run())
    print("✅ orchestrator self-test OK (quick 7 + deep 5 skenario)")
