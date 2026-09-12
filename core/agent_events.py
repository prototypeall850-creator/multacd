"""Agent event contract — satu-satunya bahasa agent runtime → UI.

Dipakai `core/agent_loop.py` (yield) dan consumer (`tui`, `tg`, tests).
Modul ini murni dataclass: tanpa import Textual, tanpa I/O, tanpa LLM —
tujuannya biar boundary tidak gampang bocor saat refactor (R2).

Test cepat:
    python -m core.agent_events
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentText:
    delta: str


@dataclass
class AgentToolStart:
    call_id: str
    name: str
    params: dict[str, Any]


@dataclass
class AgentToolDone:
    call_id: str
    name: str
    success: bool
    result: dict[str, Any] | None = None  # payload penuh (D4: expandable view)


@dataclass
class AgentDone:
    text: str


@dataclass
class AgentUsage:
    """Token resmi provider untuk satu panggilan LLM (0 = tak dilapor)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0  # estimasi lokal (tabel harga provider)


@dataclass
class AgentContinue:
    """LLM minta lanjut padahal batas iterasi tercapai.

    Bukan error — TUI tampilkan ringkasan + tombol Lanjut/Berhenti.
    CLI fallback: auto-lanjut kalau stdin bukan TTY? tidak — default berhenti.
    Lihat run_agent(continue_on_limit) + main_screen._run_turn.
    """

    tool_count: int
    limit: int
    summary: str  # ringkasan tool terakhir biar user bisa nilai


@dataclass
class AgentError:
    message: str


AgentEvent = AgentText | AgentToolStart | AgentToolDone | AgentDone | AgentUsage | AgentContinue | AgentError


if __name__ == "__main__":
    evs: list[AgentEvent] = [
        AgentText("halo"),
        AgentToolStart("c1", "list_dir", {"path": "."}),
        AgentToolDone("c1", "list_dir", True, {"success": True}),
        AgentDone("selesai"),
        AgentUsage(10, 5, 0.001),
        AgentContinue(3, 3, "list_dir"),
        AgentError("gagal"),
    ]
    assert len(evs) == 7
    assert isinstance(evs[0], AgentText) and evs[0].delta == "halo"
    assert isinstance(evs[5], AgentContinue) and evs[5].limit == 3
    print("✅ agent_events self-test OK (7 event contract)")
