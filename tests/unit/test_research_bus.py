"""Unit: research bus task-scoped — dua sesi tak saling timpa (R6)."""

from __future__ import annotations

import asyncio

from core.research.bus import get_research_sink, set_research_sink
from tools.research.quick_research import _run_coro


def _run(coro):
    return asyncio.run(coro)


def test_tasks_do_not_clobber_each_other():
    async def _main():
        async def _isi(nama: str, wadah: list) -> None:
            set_research_sink(wadah.append)
            await asyncio.sleep(0.01)  # interleave
            get_research_sink()({"type": nama})

        a: list = []
        b: list = []
        await asyncio.gather(_isi("a", a), _isi("b", b))
        assert a == [{"type": "a"}]
        assert b == [{"type": "b"}]

    _run(_main())
    assert get_research_sink() is None  # konteks luar tak tercemar


def test_reset_only_affects_own_task():
    async def _main():
        set_research_sink(lambda ev: None)
        assert get_research_sink() is not None
        set_research_sink(None)
        assert get_research_sink() is None

    _run(_main())
    assert get_research_sink() is None


def test_sink_survives_run_coro_pool_boundary():
    """Rantai TUI: task → to_thread → _run_coro(pool) → sink tetap sama."""

    async def _coro_read():
        from core.research.bus import get_research_sink as _get
        return _get()

    async def _main():
        marker = object()
        set_research_sink(marker)  # type: ignore[arg-type]
        # _run_coro dari dalam loop = jalur agent_loop (pool thread).
        assert _run_coro(_coro_read()) is marker
        # to_thread juga mewarisi context.
        seen = await asyncio.to_thread(get_research_sink)
        assert seen is marker
        set_research_sink(None)

    _run(_main())


def test_no_sink_outside_turn():
    async def _coro_read():
        from core.research.bus import get_research_sink as _get
        return _get()

    # Konteks sync tanpa set → asyncio.run biasa → None.
    assert _run_coro(_coro_read()) is None
