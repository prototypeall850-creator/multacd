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
from core.prompt_composer import PromptComposer
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
    # #25: assistant tanpa tool TIDAK boleh bawa key tool_calls
    # (provider strict 400 kalau array kosong ikut terkirim).
    assts = [m for m in ctx.get_messages() if m.get("role") == "assistant"]
    assert assts and all("tool_calls" not in m for m in assts), assts


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


def test_mode_switch_refreshes_system_prompt(sample_config, fake_llm_factory):
    # #26: ganti mode harus ganti system yang dilihat LLM berikutnya.
    composer = PromptComposer(soul="S")
    composer.update_mode("MODE-A")
    ctx = ConversationContext()
    fake = fake_llm_factory([StreamDone("a", [])])
    _run(_drain(run_agent("hi", ctx, sample_config, llm_client=fake,
                          composer=composer)))
    assert "MODE-A" in ctx.get_messages()[0]["content"]
    composer.update_mode("MODE-B")
    fake = fake_llm_factory([StreamDone("b", [])])
    _run(_drain(run_agent("halo lagi", ctx, sample_config, llm_client=fake,
                          composer=composer)))
    sys_msgs = [m for m in ctx.get_messages() if m["role"] == "system"]
    assert len(sys_msgs) == 1 and "MODE-B" in sys_msgs[0]["content"], sys_msgs
    assert "MODE-B" in fake.seen[-1][0]["content"]


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
