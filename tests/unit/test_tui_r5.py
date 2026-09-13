"""Unit: context sidebar TUI-R5 — snapshot jujur (headless)."""

from __future__ import annotations

from core.session_state import AgentStatus
from tui.widgets.info_panel import render_snapshot
from tui.widgets.status_bar import agent_status_for


def test_agent_status_words():
    assert agent_status_for(AgentStatus.IDLE) == "idle"
    assert agent_status_for(AgentStatus.EXECUTING_TOOL) == "thinking"
    assert agent_status_for(AgentStatus.WAITING_PERMISSION) == "waiting"


def test_usage_split_official_vs_unknown():
    off = render_snapshot({"mode": "code", "project": "p", "git": "g",
                           "tokens": "1.200", "prompt": "1.000",
                           "completion": "200", "cost": "—", "messages": 1,
                           "tools": 0, "model": "m", "status": "idle"})
    assert "In: 1.000 · Out: 200" in off and "~" not in off.split("In:")[1].split("\n")[0]
    unk = render_snapshot({"mode": "code", "project": "p", "git": "g",
                           "tokens": "~800", "prompt": "—", "completion": "—",
                           "cost": "—", "messages": 1, "tools": 0,
                           "model": "m", "status": "idle"})
    assert "In: — · Out: —" in unk
    assert "Context: ~800 tokens" in unk


def test_no_limit_no_percent_no_fake():
    s = render_snapshot({"mode": "code", "project": "p", "git": "g",
                         "tokens": 0, "prompt": "—", "completion": "—",
                         "cost": "—", "messages": 0, "tools": 0,
                         "model": "m", "status": "idle"})
    assert "%" not in s and "Limit" not in s


def test_r7_recompose_dedup():
    """TUI-R7: project/mode/status canonical di top bar — bukan di sidebar."""
    s = render_snapshot({"mode": "code", "project": "p", "git": "g",
                         "tokens": "10", "prompt": "—", "completion": "—",
                         "cost": "—", "messages": 2, "tools": 1,
                         "model": "glm-4.7", "status": "thinking"})
    first = s.split("\n")[0]
    assert first.startswith("Session:")  # tanpa baris project
    assert "──" not in s  # tanpa separator dekoratif
    assert "Agent: glm-4.7" in s
    assert "thinking" not in s and "code ·" not in s  # dedup mode+status
