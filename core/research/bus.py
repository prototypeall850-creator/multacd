"""Bus event research — jembatan orchestrator → TUI (R6: task-scoped).

Alur: tool research (quick/deep) jalan sync di worker, orchestrator-nya
async (kadang di thread terpisah via _run_coro). Callback on_event harus
sampai ke widget Textual yang hidup di app loop.

Dulu global mutable (`_sink`) — satu turn nimpa turn lain kalau dua sesi
jalan bareng (mis. test paralel). Sekarang ContextVar: tiap
task asyncio bawa sink sendiri-sendiri. Rantai propagasi dijaga dua titik:

- `asyncio.to_thread(execute_tool)` (agent_loop) = copy context otomatis.
- `_run_coro` (tools/research) = copy explisit (pool thread tidak warisi
  context sendiri) — lihat quick_research._run_coro.

API (set/get) tidak berubah — caller (controller, tool wrapper) sama.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable
from typing import Any

_sink: contextvars.ContextVar[
    Callable[[dict[str, Any]], None] | None
] = contextvars.ContextVar("research_sink", default=None)


def set_research_sink(fn: Callable[[dict[str, Any]], None] | None) -> None:
    """Pasang/cabut sink buat task ini saja (None = cabut)."""
    _sink.set(fn)


def get_research_sink() -> Callable[[dict[str, Any]], None] | None:
    """Dibaca tool wrapper research saat panggil orchestrator."""
    return _sink.get()


if __name__ == "__main__":
    import asyncio as _asyncio

    assert get_research_sink() is None
    evs: list = []
    set_research_sink(evs.append)
    assert get_research_sink() is not None
    get_research_sink()({"type": "x"})
    assert evs == [{"type": "x"}]
    set_research_sink(None)
    assert get_research_sink() is None

    # Task-scoped: dua task tak saling timpa.
    async def _main() -> None:
        async def _isi(nama: str, wadah: list) -> None:
            set_research_sink(wadah.append)
            await _asyncio.sleep(0.01)  # kasih jeda biar interleave
            get_research_sink()({"type": nama})  # type: ignore[operator]

        a: list = []
        b: list = []
        await _asyncio.gather(_isi("a", a), _isi("b", b))
        assert a == [{"type": "a"}], a
        assert b == [{"type": "b"}], b
        assert get_research_sink() is None  # task utama tak tercemar

    _asyncio.run(_main())
    print("✅ research bus self-test OK (task-scoped)")
