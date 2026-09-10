"""Bus event research — jembatan orchestrator → TUI.

Alur: tool research (quick/deep) jalan sync di worker, orchestrator-nya
async (kadang di thread terpisah via _run_coro). Callback on_event harus
sampai ke widget Textual yang hidup di app loop.

Pola: MainScreen pasang sink sebelum run_agent, cabut sesudahnya.
Satu turn = satu sink (guard _turn_running cegah turn ganda).
Sink dipanggil dari thread manapun — MainScreen teruskan via
call_from_thread sehingga aman.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_sink: Callable[[dict[str, Any]], None] | None = None


def set_research_sink(fn: Callable[[dict[str, Any]], None] | None) -> None:
    """Pasang/cabut sink (None = cabut). Dipanggil MainScreen."""
    global _sink
    _sink = fn


def get_research_sink() -> Callable[[dict[str, Any]], None] | None:
    """Dibaca tool wrapper research saat panggil orchestrator."""
    return _sink


if __name__ == "__main__":
    assert get_research_sink() is None
    evs: list = []
    set_research_sink(evs.append)
    assert get_research_sink() is not None
    get_research_sink()({"type": "x"})
    assert evs == [{"type": "x"}]
    set_research_sink(None)
    assert get_research_sink() is None
    print("✅ research bus self-test OK")
