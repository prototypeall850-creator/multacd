"""C1 (issue #56): Esc saat tool jalan — context tidak boleh teracuni.

Cancel mendarat di `asyncio.to_thread` (thread tool tak bisa dibunuh) →
call ke-N (dan sisanya di batch) tak pernah dapat tool_result → provider
menolak SEMUA request berikutnya (assistant tool_calls tanpa tool message
= 400). run_agent wajib mengisi tool_result yang bolong lalu re-raise.

Headless pure: stub tool lambat via registry plugin, tanpa TUI.
"""

from __future__ import annotations

import asyncio
import os
import threading

import pytest

os.environ.setdefault("MULTACD_HOME", "/tmp/opencode/test-c1")

from core.agent_loop import run_agent
from core.config import Config
from core.llm_client import StreamDone, ToolCallRequest
from core.permissions import (
    register_plugin_permission,
    unregister_plugin_permission,
)
from memory.context import ConversationContext
from tools.registry import register_tool, unregister_tool

_SLOW_SCHEMA = {
    "type": "function",
    "function": {"name": "slow_probe", "parameters": {"type": "object",
                                                      "properties": {}}},
}


class FakeLLM:
    """LLM scripted: pop antrean StreamDone per round."""

    def __init__(self, script: list[StreamDone]) -> None:
        self.script = list(script)

    async def stream_completion(self, messages, tools=None):
        done = self.script.pop(0)
        yield StreamDone(done.text, done.tool_calls)


def _tool_msgs(ctx: ConversationContext) -> list[dict]:
    return [m for m in ctx.get_messages() if m["role"] == "tool"]


async def _run_until_tool(gen_task: asyncio.Task, seen: list,
                          call_id: str) -> None:
    """Tunggu sampai AgentToolStart call_id ter-consume, lalu margin kecil
    biar cancel benar-benar mendarat di to_thread (bukan di yield)."""
    for _ in range(500):
        await asyncio.sleep(0)
        if any(getattr(e, "call_id", "") == call_id and
               type(e).__name__ == "AgentToolStart" for e in seen):
            break
    else:
        raise AssertionError(f"tool {call_id} tak pernah start")
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_cancel_mid_tool_fills_every_missing_tool_result():
    """C1: cancel di tool ke-1 dari 2 → keduanya tetap dapat tool_result."""
    release = threading.Event()

    def _slow_tool(**kwargs):
        release.wait(timeout=10)  # blok thread sampai test lepas
        return {"success": True, "result": "ok", "error": None}

    assert register_tool("slow_probe", _slow_tool, _SLOW_SCHEMA)
    register_plugin_permission("slow_probe", "auto")
    try:
        cfg = Config(model="m", api_key="k")
        ctx = ConversationContext()
        llm = FakeLLM([StreamDone("", [
            ToolCallRequest("c1", "slow_probe", {}),
            ToolCallRequest("c2", "slow_probe", {}),
        ])])
        seen: list = []

        async def _consume() -> None:
            async for ev in run_agent("go", ctx, cfg, llm_client=llm):
                seen.append(ev)

        task = asyncio.create_task(_consume())
        try:
            await _run_until_tool(task, seen, "c1")
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()  # lepas thread (to_thread tak bisa dibunuh)

        # Kunci C1: SETIAP tool_call punya tool_result — provider sah.
        msgs = _tool_msgs(ctx)
        assert {m["tool_call_id"] for m in msgs} == {"c1", "c2"}, msgs
        assert all("Dibatalkan user" in str(m["content"]) for m in msgs)
        # Tidak ada duplikat (satu result per call).
        assert len(msgs) == 2, msgs
    finally:
        unregister_tool("slow_probe")
        unregister_plugin_permission("slow_probe")


@pytest.mark.asyncio
async def test_cancel_keeps_already_answered_results():
    """C1: call yang SUDAH dapat hasil tidak ditimpa/diduplikasi."""
    release = threading.Event()

    def _slow_tool(**kwargs):
        release.wait(timeout=10)
        return {"success": True, "result": "ok", "error": None}

    assert register_tool("slow_probe", _slow_tool, _SLOW_SCHEMA)
    register_plugin_permission("slow_probe", "auto")
    try:
        cfg = Config(model="m", api_key="k")
        ctx = ConversationContext()
        llm = FakeLLM([StreamDone("", [
            ToolCallRequest("c1", "list_dir", {"path": "."}),
            ToolCallRequest("c2", "slow_probe", {}),
        ])])
        seen: list = []

        async def _consume() -> None:
            async for ev in run_agent("go", ctx, cfg, llm_client=llm):
                seen.append(ev)

        task = asyncio.create_task(_consume())
        try:
            await _run_until_tool(task, seen, "c2")
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()

        msgs = _tool_msgs(ctx)
        assert {m["tool_call_id"] for m in msgs} == {"c1", "c2"}, msgs
        by_id = {m["tool_call_id"]: m for m in msgs}
        # c1: hasil asli utuh, BUKAN pesan cancel.
        assert "Dibatalkan user" not in str(by_id["c1"]["content"])
        # c2: diisi pesan cancel (tak bolong).
        assert "Dibatalkan user" in str(by_id["c2"]["content"])
    finally:
        unregister_tool("slow_probe")
        unregister_plugin_permission("slow_probe")


# --------------------------------------------- ronde-2 audit (MAJOR-1/2)


@pytest.mark.asyncio
async def test_cancel_at_consumer_yield_fills_via_generator_exit():
    """MAJOR-1 (ronde-2 audit): cancel mendarat di KONSUMEN (hooks.emit →
    add_tool_row dsb.) → run_agent suspend di `yield` → finalisasi async-gen
    mengirim GeneratorExit, BUKAN CancelledError. Fill wajib jalan di jalur
    itu juga (finally), bukan cuma except CancelledError.

    Deterministik: handshake via Event, cancel tepat saat emit menggantung,
    finalisasi eksplisit via aclose (di prod: finalizer GC/loop)."""
    cfg = Config(model="m", api_key="k")
    ctx = ConversationContext()
    llm = FakeLLM([StreamDone("", [
        ToolCallRequest("c1", "list_dir", {"path": "."}),
        ToolCallRequest("c2", "list_dir", {"path": "."}),
    ])])
    started = asyncio.Event()

    async def _consume(agen) -> None:
        async for ev in agen:  # konsumen ala AgentController.run_turn
            if type(ev).__name__ == "AgentToolStart":
                started.set()
            await asyncio.sleep(10)  # cancel mendarat DI SINI (window yield)

    agen = run_agent("go", ctx, cfg, llm_client=llm)
    task = asyncio.create_task(_consume(agen))
    await started.wait()  # generator suspend di yield AgentToolStart c1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await agen.aclose()  # GeneratorExit masuk ke frame → fill di finally

    msgs = _tool_msgs(ctx)
    assert {m["tool_call_id"] for m in msgs} == {"c1", "c2"}, msgs
    assert all("Dibatalkan user" in str(m["content"]) for m in msgs)
    assert len(msgs) == 2  # tanpa duplikat


@pytest.mark.asyncio
async def test_reused_call_id_across_turns_still_gets_fill():
    """MAJOR-2 (ronde-2 audit): provider lokal reuse tool_call_id lintas
    turn. Scan global `got` mengira id ronde ini sudah keisi (hasil ronde
    lalu) → fill bolong lagi. `answered` wajib per-batch tool call."""
    release = threading.Event()

    def _slow_tool(**kwargs):
        release.wait(timeout=10)  # cancel mendarat di to_thread call ini
        return {"success": True, "result": "ok", "error": None}

    assert register_tool("slow_probe", _slow_tool, _SLOW_SCHEMA)
    register_plugin_permission("slow_probe", "auto")
    try:
        cfg = Config(model="m", api_key="k")
        ctx = ConversationContext()
        llm = FakeLLM([
            StreamDone("", [ToolCallRequest("c1", "list_dir", {"path": "."})]),
            StreamDone("selesai", []),  # akhir turn 1
            StreamDone("", [  # turn 2: id "c1" di-REUSE provider
                ToolCallRequest("c1", "slow_probe", {}),
                ToolCallRequest("c2", "slow_probe", {}),
            ]),
        ])

        async def _drain() -> None:
            async for _ in run_agent("satu", ctx, cfg, llm_client=llm):
                pass

        await _drain()  # turn 1 normal: c1 keisi hasil asli
        assert [m["tool_call_id"] for m in _tool_msgs(ctx)] == ["c1"]

        seen: list = []

        async def _consume() -> None:
            async for ev in run_agent("dua", ctx, cfg, llm_client=llm):
                seen.append(ev)

        task = asyncio.create_task(_consume())
        await _run_until_tool(task, seen, "c1")  # margin → cancel di to_thread
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        release.set()  # lepas thread (to_thread tak bisa dibunuh)

    # Kunci MAJOR-2: c1 ronde-2 TETAP dapat fill (c1 ronde-1 tak dihitung).
    msgs = _tool_msgs(ctx)
    assert [m["tool_call_id"] for m in msgs] == ["c1", "c1", "c2"], msgs
    assert "Dibatalkan user" in str(msgs[1]["content"])  # c1 turn-2
    assert "Dibatalkan user" in str(msgs[2]["content"])  # c2
    # c1 turn-1: hasil asli utuh, bukan pesan cancel.
    assert "Dibatalkan user" not in str(msgs[0]["content"])
    unregister_tool("slow_probe")
    unregister_plugin_permission("slow_probe")


# ------------------------------------------ ronde-3 audit final (MINOR-1)


@pytest.mark.asyncio
async def test_internal_error_not_labeled_user_cancel():
    """MINOR-1 (audit final): exception internal (bukan cancel/GeneratorExit)
    menembus finally → tool_result jangan keisi "Dibatalkan user" —
    SYSTEM_PROMPT menyuruh model menghormati pesan itu → model menyerah
    salah. Pesan harus netral, dan exception tetap menembus ke pemanggil."""
    cfg = Config(model="m", api_key="k")
    ctx = ConversationContext()
    llm = FakeLLM([StreamDone("", [
        ToolCallRequest("c1", "write_file",
                        {"path": "x.txt", "content": "y"}),
    ])])

    async def _boom(name, params):
        raise ValueError("boom-internal")

    with pytest.raises(ValueError):  # exception tetap menembus
        async for _ in run_agent("go", ctx, cfg, llm_client=llm,
                                 confirm=_boom):
            pass

    msgs = _tool_msgs(ctx)
    assert [m["tool_call_id"] for m in msgs] == ["c1"], msgs  # fill tetap
    assert "Dibatalkan user" not in str(msgs[0]["content"])
    assert "Turn berhenti" in str(msgs[0]["content"])
    assert "error internal" in str(msgs[0]["content"])
