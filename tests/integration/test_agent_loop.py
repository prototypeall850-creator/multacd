"""Integration skeleton: agent loop end-to-end pakai FakeLLM.

- teks murni → AgentDone tanpa tool
- satu tool auto (list_dir) → jalan + hasil masuk context
- max iterations → berhenti graceful (tanpa infinite loop)

Sync wrapper (asyncio.run) — tanpa butuh pytest-asyncio.
"""

from __future__ import annotations

import asyncio

from core.agent_loop import AgentDone, AgentError, run_agent
from core.llm_client import StreamDone, ToolCallRequest
from memory.context import ConversationContext


def _run(coro):
    return asyncio.run(coro)


async def _drain(gen):
    return [e async for e in gen]


async def _yes(tool: str, params: dict) -> str:
    return "yes"


def test_plain_text_no_tool(sample_config, fake_llm_factory):
    fake = fake_llm_factory([StreamDone("halo dunia", [])])
    ctx = ConversationContext()
    events = _run(_drain(run_agent("hi", ctx, sample_config, llm_client=fake)))
    assert isinstance(events[-1], AgentDone)
    assert "halo" in events[-1].text


def test_single_auto_tool_runs(sample_config, fake_llm_factory, tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    fake = fake_llm_factory([
        StreamDone("", [ToolCallRequest(id="c1", name="list_dir",
                                        arguments={"path": str(tmp_path)})]),
        StreamDone("selesai", []),
    ])
    ctx = ConversationContext()
    events = _run(_drain(run_agent("list", ctx, sample_config,
                                   llm_client=fake, confirm=_yes)))
    assert isinstance(events[-1], AgentDone)
    blob = " ".join(str(m.get("content", "")) for m in ctx.get_messages())
    assert "a.txt" in blob or "a.txt" in events[-1].text


def test_max_iterations_stops_gracefully(sample_config, fake_llm_factory):
    sample_config.max_tool_iterations = 2
    script = [StreamDone("", [ToolCallRequest(id=f"c{i}", name="list_dir",
                                              arguments={"path": "."})])
              for i in range(5)]
    fake = fake_llm_factory(script)
    ctx = ConversationContext()
    events = _run(_drain(run_agent("loop", ctx, sample_config,
                                   llm_client=fake, confirm=_yes)))
    assert any(isinstance(e, AgentError) for e in events)
    assert "batas 2 iterasi" in events[-1].message
