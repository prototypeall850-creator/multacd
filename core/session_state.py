"""Session state — satu sumber kebenaran status agent per sesi (R3).

Dulu status turn/token/cost/tool tersebar di `MainScreen`
(`_turn_running`, `_tools_run`, `_sess_*`). Sekarang satu object:

    state = SessionState()
    state = reduce_event(state, event)  # tiap AgentEvent
    ui.render(state)                    # widget baca state, bukan sebaliknya

Tanpa import Textual — headless testable. Mode/model tetap milik
config/mode_manager (tidak diduplikat di sini).

Test cepat:
    python -m core.session_state
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from core.agent_events import (
    AgentContinue,
    AgentDone,
    AgentError,
    AgentEvent,
    AgentText,
    AgentToolDone,
    AgentToolStart,
    AgentUsage,
)


class AgentStatus(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING_TOOL = "executing"
    WAITING_PERMISSION = "waiting_permission"
    WAITING_USER = "waiting_user"


@dataclass
class SessionState:
    """Status agent + metrik sesi. Satu instance per sesi TUI."""

    status: AgentStatus = AgentStatus.IDLE
    current_tool: str | None = None
    current_call_id: str | None = None
    tool_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    # Izin [A] per sesi (#32): resolver hidup di sini nantinya (R4).
    # Dicatat dulu biar kontraknya jelas — belum dipakai runtime.
    session_approved: set[str] = field(default_factory=set)

    @property
    def busy(self) -> bool:
        """True selama turn jalan (dipakai submit-guard + quit-guard)."""
        return self.status is not AgentStatus.IDLE

    def begin_turn(self) -> None:
        self.status = AgentStatus.THINKING
        self.current_tool = None
        self.current_call_id = None

    def end_turn(self) -> None:
        self.status = AgentStatus.IDLE
        self.current_tool = None
        self.current_call_id = None


def reduce_event(state: SessionState, event: AgentEvent) -> SessionState:
    """Lipat satu AgentEvent ke state. Return state yang sama (boleh chaining)."""
    if isinstance(event, AgentToolStart):
        state.status = AgentStatus.EXECUTING_TOOL
        state.current_tool = event.name
        state.current_call_id = event.call_id
    elif isinstance(event, AgentToolDone):
        state.status = AgentStatus.THINKING
        state.current_tool = None
        state.current_call_id = None
        state.tool_count += 1
    elif isinstance(event, AgentUsage):
        state.prompt_tokens += event.prompt_tokens
        state.completion_tokens += event.completion_tokens
        state.cost_usd += event.cost_usd
    elif isinstance(event, AgentContinue):
        state.status = AgentStatus.WAITING_USER
        state.current_tool = None
        state.current_call_id = None
    elif isinstance(event, (AgentDone, AgentError)):
        state.status = AgentStatus.IDLE
        state.current_tool = None
        state.current_call_id = None
    elif isinstance(event, AgentText):
        if state.status in (AgentStatus.IDLE, AgentStatus.WAITING_USER):
            state.status = AgentStatus.THINKING
    return state


if __name__ == "__main__":
    s = SessionState()
    assert not s.busy and s.status is AgentStatus.IDLE
    s.begin_turn()
    assert s.busy
    reduce_event(s, AgentText("hai"))
    assert s.status is AgentStatus.THINKING
    reduce_event(s, AgentToolStart("c1", "bash", {"command": "ls"}))
    assert s.status is AgentStatus.EXECUTING_TOOL
    assert s.current_tool == "bash" and s.current_call_id == "c1"
    reduce_event(s, AgentUsage(10, 5, 0.001))
    assert (s.prompt_tokens, s.completion_tokens) == (10, 5)
    reduce_event(s, AgentToolDone("c1", "bash", True, {"success": True}))
    assert s.tool_count == 1 and s.current_tool is None
    assert s.status is AgentStatus.THINKING
    reduce_event(s, AgentContinue(3, 3, "bash"))
    assert s.status is AgentStatus.WAITING_USER and s.busy
    s.begin_turn()  # lanjut → thinking lagi
    reduce_event(s, AgentDone("ok"))
    assert s.status is AgentStatus.IDLE and not s.busy
    s.begin_turn()
    reduce_event(s, AgentError("boom"))
    assert s.status is AgentStatus.IDLE
    s.end_turn()
    assert not s.busy
    print("✅ session_state self-test OK (reducer + lifecycle)")
