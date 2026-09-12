"""Unit: AgentController — loop turn headless tanpa Textual (R4)."""

from __future__ import annotations

import asyncio

from core.agent_events import AgentContinue, AgentDone
from core.llm_client import StreamDone, ToolCallRequest
from core.session_state import AgentStatus, SessionState
from memory.context import ConversationContext
from tui.controllers.agent_controller import AgentController, TurnHooks


def _run(coro):
    return asyncio.run(coro)


async def _no_continue(ev: AgentContinue) -> bool:
    raise AssertionError("tak boleh Continue di sini")


async def _no_ask(question: str) -> str:
    raise AssertionError("tak boleh ask")


def _no_live(call_id: str, line: str) -> None:
    pass


def _hooks(emit, confirm, cont=_no_continue):
    return TurnHooks(emit=emit, continue_prompt=cont, confirm=confirm,
                     ask_user=_no_ask, live=_no_live)


def test_plain_turn_emits_and_idles(sample_config, fake_llm_factory):
    ctx = ConversationContext()
    ctl = AgentController(SessionState(), sample_config, ctx)
    ctl.llm_client = fake_llm_factory([StreamDone("halo dunia", [])])
    seen: list[str] = []

    async def _emit(ev):
        seen.append(type(ev).__name__)

    async def _deny(name, params):
        raise AssertionError("tak boleh confirm")

    _run(ctl.run_turn("hi", _hooks(_emit, _deny)))
    assert seen[0] == "AgentText" and seen[-1] == "AgentDone", seen
    assert ctl.session.status is AgentStatus.IDLE


def test_session_approve_persists_across_turns(sample_config,
                                               fake_llm_factory):
    """Regression #32: [A] di turn 1 → turn 2 auto tanpa confirm."""
    ctx = ConversationContext()
    ctl = AgentController(SessionState(), sample_config, ctx)
    seen: list[str] = []

    async def _emit(ev):
        seen.append(type(ev).__name__)

    ctl.llm_client = fake_llm_factory([
        StreamDone("", [ToolCallRequest(id="c1", name="bash",
                                        arguments={"command": "echo a"})]),
        StreamDone("satu", []),
    ])
    calls: list[str] = []

    async def _all(name, params):
        calls.append(name)
        return "all"

    _run(ctl.run_turn("run", _hooks(_emit, _all), active_tools=["bash"]))
    assert calls == ["bash"]
    assert isinstance(seen[-1], str) and "AgentToolDone" in seen

    ctl.llm_client = fake_llm_factory([
        StreamDone("", [ToolCallRequest(id="c2", name="bash",
                                        arguments={"command": "echo b"})]),
        StreamDone("dua", []),
    ])

    async def _boom(name, params):
        raise AssertionError("turn 2 harus auto (approve sesi persist)")

    _run(ctl.run_turn("lagi", _hooks(_emit, _boom), active_tools=["bash"]))
    assert ctx.get_messages()[-2]["content"] == "b"  # hasil echo b


def test_continue_prompt_continues_without_reset(sample_config,
                                                 fake_llm_factory):
    sample_config.max_tool_iterations = 1
    ctx = ConversationContext()
    ctl = AgentController(SessionState(), sample_config, ctx)
    ctl.llm_client = fake_llm_factory([
        StreamDone("", [ToolCallRequest(id="c1", name="list_dir",
                                        arguments={"path": "."})]),
        StreamDone("", [ToolCallRequest(id="c2", name="list_dir",
                                        arguments={"path": "."})]),
        StreamDone("selesai", []),
    ])
    dones = 0

    async def _emit(ev):
        nonlocal dones
        if isinstance(ev, AgentDone):
            dones += 1

    async def _yes(name, params):
        return "yes"

    async def _lanjut(ev: AgentContinue) -> bool:
        assert ev.limit == 1
        return True

    _run(ctl.run_turn("loop", _hooks(_emit, _yes, _lanjut)))
    assert dones == 1  # AgentContinue di-swalallow controller, user terima Done
    assert ctl.session.status is AgentStatus.IDLE
