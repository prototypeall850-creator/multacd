"""AgentController — konsumsi run_agent di luar widget (R4).

MainScreen tinggal: siapkan widget + inject hooks + render event.
Controller yang pegang: loop turn, Continue-loop, research sink,
live output, dan PermissionChecker lintas turn (fix #32: approve [A]
tidak lagi hilang tiap turn).

Tanpa import Textual — headless testable. Semua yang butuh UI
(dialog, widget, app loop) masuk lewat TurnHooks dari screen.

Test cepat:
    python -m tui.controllers.agent_controller
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from core.agent_events import AgentContinue, AgentEvent
from core.agent_loop import (
    AskCallback,
    ConfirmCallback,
    run_agent,
)
from core.config import Config
from core.permissions import PermissionChecker
from core.research.bus import set_research_sink
from core.session_state import SessionState, reduce_event
from memory.context import ConversationContext


@dataclass
class TurnHooks:
    """Jembatan controller → UI. Diisi MainScreen tiap turn."""

    # Tiap AgentEvent (state sudah direduce duluan) → render widget.
    emit: Callable[[AgentEvent], Awaitable[None]]
    # Batas iterasi tercapai → True = lanjut tanpa reset konteks.
    continue_prompt: Callable[[AgentContinue], Awaitable[bool]]
    # Izin tool / pertanyaan balik → dialog TUI.
    confirm: ConfirmCallback
    ask_user: AskCallback
    # Live output per baris (sudah aman-thread dari sisi screen).
    live: Callable[[str, str], None]
    # Event research orchestrator → panel (None = sink tidak dipasang).
    research: Callable[[dict[str, Any]], None] | None = None


class AgentController:
    """Pemilik loop agent satu sesi. Satu instance per MainScreen."""

    def __init__(self, session: SessionState, config: Config,
                 context: ConversationContext) -> None:
        self.session = session
        self.config = config
        self.context = context
        # Persistent lintas turn — approve [A] hidup selama sesi (#32).
        self.checker = PermissionChecker(config)
        self.llm_client: Any = None
        self.composer: Any = None
        self.mode_manager: Any = None

    async def run_turn(self, text: str, hooks: TurnHooks,
                       active_tools: list[str] | None = None) -> None:
        """Satu turn penuh + lanjutan Continue. Idempotent di finally."""
        self.checker.config = self.config  # hormati flag config terbaru
        self.session.begin_turn()
        if hooks.research is not None:
            set_research_sink(hooks.research)
        try:
            pending = text
            first = True
            keep_going = True
            while keep_going:
                keep_going = False
                async for event in run_agent(
                    pending,
                    self.context,
                    self.config,
                    llm_client=self.llm_client,
                    confirm=hooks.confirm,
                    ask_user=hooks.ask_user,
                    mode_manager=self.mode_manager if first else None,
                    active_tools=active_tools,
                    composer=self.composer,
                    output_cb=hooks.live,
                    continue_on_limit=not first,
                    checker=self.checker,
                ):
                    first = False
                    reduce_event(self.session, event)
                    if isinstance(event, AgentContinue):
                        if await hooks.continue_prompt(event):
                            pending = (
                                "Lanjutkan tugas sebelumnya sampai selesai. "
                                "Jangan ulangi tool yang hasilnya sudah ada.")
                            keep_going = True
                        break
                    await hooks.emit(event)
        finally:
            set_research_sink(None)
            self.session.end_turn()


if __name__ == "__main__":
    import asyncio as _asyncio

    from core.llm_client import StreamDone
    from core.llm_client import ToolCallRequest as _TCR

    class _FakeLLM:
        def __init__(self, script: list) -> None:
            self.script = list(script)

        async def stream_completion(self, messages, tools=None):
            from core.llm_client import StreamText as _ST
            done = self.script.pop(0)
            for word in done.text.split():
                yield _ST(word + " ")
            yield done

    async def _main() -> None:
        from core.config import Config as _Cfg
        cfg = _Cfg(model="m", api_key="k")
        ctx = ConversationContext()
        ctl = AgentController(SessionState(), cfg, ctx)
        ctl.llm_client = _FakeLLM([StreamDone("halo", [])])
        seen: list = []

        async def _emit(ev):
            seen.append(type(ev).__name__)

        async def _no_continue(ev):
            raise AssertionError("tak boleh Continue di sini")

        hooks = TurnHooks(emit=_emit, continue_prompt=_no_continue,
                          confirm=_deny, ask_user=_no_ask, live=_live_noop)
        await ctl.run_turn("hi", hooks)
        assert seen[0] == "AgentText" and seen[-1] == "AgentDone", seen
        assert not ctl.session.busy

        # [A] lintas turn (#32): turn 1 "all" → turn 2 tanpa confirm.
        cfg2 = _Cfg(model="m", api_key="k")
        ctx2 = ConversationContext()
        ctl2 = AgentController(SessionState(), cfg2, ctx2)
        ctl2.llm_client = _FakeLLM([
            StreamDone("", [_TCR("c1", "bash", {"command": "echo a"})]),
            StreamDone("satu", []),
        ])
        calls: list[str] = []

        async def _all(name, params):
            calls.append(name)
            return "all"

        hooks2 = TurnHooks(emit=_emit, continue_prompt=_no_continue,
                           confirm=_all, ask_user=_no_ask, live=_live_noop)
        await ctl2.run_turn("run", hooks2, active_tools=["bash"])
        assert calls == ["bash"], calls
        ctl2.llm_client = _FakeLLM([
            StreamDone("", [_TCR("c2", "bash", {"command": "echo b"})]),
            StreamDone("dua", []),
        ])

        async def _boom(name, params):
            raise AssertionError("turn 2 harus auto (approve sesi)")

        hooks2.confirm = _boom
        await ctl2.run_turn("lagi", hooks2, active_tools=["bash"])
        assert ctx2.get_messages()[-2]["content"] == "b"  # hasil echo b
        print("✅ agent_controller self-test OK (turn + approve lintas turn)")

    async def _deny(name, params):
        raise AssertionError(f"tak boleh confirm: {name}")

    async def _no_ask(question):
        raise AssertionError("tak boleh ask")

    def _live_noop(call_id, line):
        pass

    _asyncio.run(_main())
