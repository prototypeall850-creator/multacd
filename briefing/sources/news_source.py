"""News source — riset berita per topik, paralel (PLAN Phase 4 Step 7).

research_fn(topic) -> str di-inject biar test tanpa network.
Default: orchestrator quick_research (active config → setup_client).

Test cepat:
    python -m briefing.sources.news_source
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

ResearchFn = Callable[[str], Awaitable[str]]


async def _default_research(topic: str, max_sources: int = 3) -> str:
    from core.config import get_active_config, load_config
    from core.llm_client import setup_client
    from core.research.orchestrator import quick_research as _qr

    config = get_active_config() or load_config()
    llm = setup_client(config)
    res = await _qr(f"latest news about {topic}", config=config, llm=llm)
    answer = (res.answer or "").strip()
    shown = (res.sources[:max_sources]
             if max_sources > 0 and len(res.sources) > max_sources
             else res.sources)
    if shown:
        names = ", ".join(getattr(s, "title", "?") or "?" for s in shown)
        answer += f" ({len(shown)} sumber: {names})"
    return answer or "(tidak ada berita ditemukan)"


async def get_news(topics: list[str],
                   research_fn: ResearchFn | None = None,
                   max_sources: int = 3) -> dict[str, str]:
    """Riset semua topik paralel. Gagal satu → pesan, bukan raise."""
    async def _one(topic: str) -> tuple[str, str]:
        try:
            if research_fn is not None:
                return topic, await research_fn(topic)
            return topic, await _default_research(topic, max_sources)
        except Exception as e:
            return topic, f"(gagal riset: {e})"

    results = await asyncio.gather(*[_one(t) for t in topics])
    return dict(results)


def get_news_sync(topics: list[str], research_fn: Any = None,
                  max_sources: int = 3) -> dict[str, str]:
    """Wrapper sync (dipakai generator yang jalan di job thread)."""
    from tools.research.quick_research import _run_coro
    return _run_coro(get_news(topics, research_fn, max_sources))


if __name__ == "__main__":
    async def _fake(topic: str) -> str:
        if topic == "rusak":
            raise RuntimeError("jaringan putus")
        return f"berita {topic}: model baru rilis"

    async def _go() -> None:
        out = await get_news(["AI", "rusak"], _fake)
        assert out["AI"] == "berita AI: model baru rilis"
        assert "gagal riset" in out["rusak"]
        assert await get_news([], _fake) == {}

    asyncio.run(_go())
    out = get_news_sync(["AI"], _fake)
    assert out == {"AI": "berita AI: model baru rilis"}, out

    print("✅ news_source self-test OK (paralel + gagal-satu)")
