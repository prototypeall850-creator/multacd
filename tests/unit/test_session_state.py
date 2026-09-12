"""Unit: SessionState reducer — event → state tanpa Textual (R3)."""

from __future__ import annotations

from core.agent_events import (
    AgentContinue,
    AgentDone,
    AgentError,
    AgentText,
    AgentToolDone,
    AgentToolStart,
    AgentUsage,
)
from core.session_state import AgentStatus, SessionState, reduce_event


def test_idle_not_busy():
    s = SessionState()
    assert s.status is AgentStatus.IDLE and not s.busy


def test_tool_lifecycle():
    s = SessionState()
    s.begin_turn()
    assert s.busy
    reduce_event(s, AgentToolStart("c1", "bash", {"command": "ls"}))
    assert s.status is AgentStatus.EXECUTING_TOOL
    assert s.current_tool == "bash" and s.current_call_id == "c1"
    reduce_event(s, AgentToolDone("c1", "bash", True, {"success": True}))
    assert s.status is AgentStatus.THINKING and s.tool_count == 1
    assert s.current_tool is None


def test_usage_accumulates():
    s = SessionState()
    reduce_event(s, AgentUsage(10, 5, 0.001))
    reduce_event(s, AgentUsage(3, 2, 0.0))
    assert (s.prompt_tokens, s.completion_tokens) == (13, 7)
    assert abs(s.cost_usd - 0.001) < 1e-9


def test_done_and_error_end_busy():
    for ev in (AgentDone("ok"), AgentError("boom")):
        s = SessionState()
        s.begin_turn()
        reduce_event(s, ev)
        assert s.status is AgentStatus.IDLE and not s.busy


def test_continue_waits_user_but_stays_busy():
    s = SessionState()
    s.begin_turn()
    reduce_event(s, AgentContinue(3, 3, "bash"))
    assert s.status is AgentStatus.WAITING_USER and s.busy
    # Lanjut → teks masuk → thinking lagi.
    reduce_event(s, AgentText("lanjut"))
    assert s.status is AgentStatus.THINKING


def test_end_turn_resets():
    s = SessionState()
    s.begin_turn()
    reduce_event(s, AgentToolStart("c1", "bash", {}))
    s.end_turn()
    assert s.status is AgentStatus.IDLE
    assert s.current_tool is None and s.current_call_id is None
