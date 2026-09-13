"""Unit: background work TUI-R10 (§29-30) — headless pilot."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("MULTACD_HOME", "/tmp/opencode/test-r10")

from core.config import Config
from core.session_state import AgentStatus
from tui.app import MultacdApp
from tui.widgets.chat_panel import ChatPanel
from tui.widgets.input_bar import InputBar
from tui.widgets.thinking_bar import base_label


@pytest.fixture()
def app():
    return MultacdApp(Config(model="groq/llama-3.3-70b", api_key="k"))


def test_background_label():
    """§30: 'background' punya label sendiri, bukan 'running background...'."""
    assert base_label("background") == "background"


@pytest.mark.asyncio
async def test_ctrl_b_toggle_ui_only(app):
    """Ctrl+B: UI dilepas, task/state TIDAK disentuh (§29 bukan cancel)."""
    async with app.run_test() as pilot:
        s = app.main_screen
        s.session.begin_turn()  # simulasi turn jalan (tanpa LLM)
        s.session.status = AgentStatus.THINKING
        await pilot.press("ctrl+b")
        await pilot.pause()
        assert s._bg_active is True
        assert s.query_one(InputBar).disabled is False  # input bebas
        assert s.session.status is AgentStatus.THINKING  # state utuh
        # toggle balik ke foreground
        await pilot.press("ctrl+b")
        await pilot.pause()
        assert s._bg_active is False
        assert s.query_one(InputBar).disabled is True


@pytest.mark.asyncio
async def test_submit_block_while_background(app):
    """§29: UI usable, tapi pesan LLM baru di-block jujur saat turn jalan."""
    async with app.run_test() as pilot:
        s = app.main_screen
        s.session.begin_turn()
        s.session.status = AgentStatus.THINKING
        s._bg_active = True
        from tui.widgets.chat_panel import ChatPanel
        chat = s.query_one(ChatPanel)
        await chat.dismiss_splash()
        before = len(list(chat.children))
        s._submit("buatkan fitur baru")
        await pilot.pause()
        assert len(list(chat.children)) == before + 1  # info line muncul
        assert s.session.busy  # masih jalan, tidak ada turn kedua
        assert s._turn_running


@pytest.mark.asyncio
async def test_completion_resets_and_notifies(app):
    """§30: selesai → flag reset + info '✓ Background selesai' + toast.

    End-to-end: FakeAgent turn nyata lewat _run_turn asli (emit + finally).
    """
    import asyncio

    from core.agent_events import AgentText

    class FakeAgent:
        """Turn instan tanpa LLM; ditahan sampai test lepas."""

        llm_client = composer = None

        def __init__(self, session):
            self.session = session
            self.release = asyncio.Event()

        async def run_turn(self, text, hooks, active_tools=None):
            self.session.begin_turn()
            await self.release.wait()  # tahan di tengah turn
            await hooks.emit(AgentText(delta="hai dari fake"))

    async with app.run_test() as pilot:
        s = app.main_screen
        fake = FakeAgent(s.session)
        s._agent_ctl = fake
        chat = s.query_one(ChatPanel)
        await chat.dismiss_splash()
        s._submit("tes bg")
        await pilot.pause()
        await pilot.pause()
        assert s.session.busy and s._turn_running
        s.action_background_task()  # Ctrl+B path
        assert s._bg_active is True
        assert s.query_one(InputBar).disabled is False
        fake.release.set()  # lepas → turn selesai → finally asli jalan
        for _ in range(6):
            await pilot.pause()
        import asyncio as _aio
        await _aio.sleep(0.05)  # app.notify deferred (call_later)
        assert s._bg_active is False
        assert not s.session.busy
        texts = [str(getattr(c.render(), "plain", c.render()))
                 for c in chat.children]
        assert any("✓ Background selesai" in t for t in texts), texts
        assert any("llama-3.3-70b" in t for t in texts)  # meta jawaban ter-close
        assert len(app._notifications) >= 1
