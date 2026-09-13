"""Unit: fresh screen ala OpenCode TUI-R13 — headless pilot."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("MULTACD_HOME", "/tmp/opencode/test-r13")

from core.config import Config
from tui.app import MultacdApp
from tui.widgets.chat_panel import ChatPanel
from tui.widgets.fresh_layer import (
    FreshScreen,
    input_meta_text,
    logo_lines,
    render_logo_adaptive,
)


@pytest.fixture()
def app():
    return MultacdApp(Config(model="groq/llama-3.3-70b", api_key="k"))


def test_logo_shape():
    """Logo block art: 6 baris, lebar konsisten, adaptif layar sempit."""
    lines = logo_lines()
    assert len(lines) == 6 and len({len(x) for x in lines}) == 1
    assert logo_lines("x!") == []  # huruf tak ada → kosong (jangan rusak UI)
    assert render_logo_adaptive(100).plain.count("\n") == 5
    assert render_logo_adaptive(40).plain == "multacd"  # Termux portrait


def test_input_meta_text():
    assert input_meta_text("code", "openai/gpt-5") == "code · gpt-5"
    assert input_meta_text("code", "") == "code · ?"


@pytest.mark.asyncio
async def test_fresh_screen_on_start(app):
    """R13: layar awal = FreshScreen di atas MainScreen."""
    async with app.run_test() as pilot:
        for _ in range(5):
            await pilot.pause()
        assert isinstance(app.screen, FreshScreen)
        assert app.screen.query_one("#fresh-input") is not None
        assert app.main_screen is not None


@pytest.mark.asyncio
async def test_submit_pops_to_main(app):
    """R13: submit di layar awal → pop + _submit jalan di MainScreen."""
    async with app.run_test() as pilot:
        for _ in range(5):
            await pilot.pause()

        class FakeAgent:  # turn tanpa LLM
            llm_client = composer = None

            async def run_turn(self, text, hooks, active_tools=None):
                self.session.begin_turn()

        fake = FakeAgent()
        fake.session = app.main_screen.session
        app.main_screen._agent_ctl = fake
        app.screen.query_one("#fresh-input").text = "halo bro"
        await pilot.press("enter")
        for _ in range(6):
            await pilot.pause()
        assert type(app.screen) is not FreshScreen  # sudah pop
        texts = [str(getattr(c.render(), "plain", c.render()))
                 for c in app.main_screen.query_one(ChatPanel).children]
        assert any("halo bro" in t for t in texts), texts  # user msg masuk


@pytest.mark.asyncio
async def test_main_screen_input_meta(app):
    """Meta `code · model` dalam input box MainScreen terisi."""
    async with app.run_test() as pilot:
        for _ in range(3):
            await pilot.pause()
        from textual.widgets import Static
        meta = app.main_screen.query_one("#input-meta", Static)
        assert "llama-3.3-70b" in str(getattr(meta.render(), "plain", ""))
