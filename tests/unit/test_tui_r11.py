"""Unit: permission UX TUI-R11 (§23-24) — headless pilot."""

from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("MULTACD_HOME", "/tmp/opencode/test-r11")

from core.config import Config
from tui.app import MultacdApp
from tui.widgets.input_bar import InputBar
from tui.widgets.permission_popup import PermissionPopup, scope_of


@pytest.fixture()
def app():
    return MultacdApp(Config(model="groq/llama-3.3-70b", api_key="k"))


async def _open(app, pilot, tool="bash",
                params=None):
    """Mulai ask() di background worker; balikin popup + future handle."""
    perm = app.main_screen.query_one(PermissionPopup)
    task = asyncio.ensure_future(perm.ask(tool, params or {"command": "ls"}))
    for _ in range(4):
        await pilot.pause()
    return perm, task


@pytest.mark.asyncio
async def test_fullscreen_toggle_and_esc(app):
    """§24: Ctrl+F → fullscreen; Esc di fullscreen = compact, BUKAN no."""
    async with app.run_test() as pilot:
        perm, task = await _open(app, pilot)
        assert perm.display
        assert not perm.has_class("fullscreen")
        await pilot.press("ctrl+f")
        await pilot.pause()
        assert perm.has_class("fullscreen")
        # detail params utuh tampil
        from tui.widgets.permission_popup import detail_text  # noqa: F401
        detail = perm.query_one("#perm-detail-text")
        assert "command:" in str(getattr(detail.render(), "plain", ""))
        # Esc saat fullscreen → balik compact, popup MASIH menunggu
        await pilot.press("escape")
        await pilot.pause()
        assert not perm.has_class("fullscreen")
        assert perm.is_waiting
        # Esc saat compact → jawaban no
        await pilot.press("escape")
        await pilot.pause()
        assert await asyncio.wait_for(task, 2) == "no"


@pytest.mark.asyncio
async def test_title_scope_hint_visible(app):
    """§23: header 'Permission required' + esc, scope line, hint keys."""
    async with app.run_test() as pilot:
        perm, task = await _open(app, pilot, "bash", {"command": "pytest"})
        title = perm.query_one("#perm-title-text")
        assert "Permission required" in str(
            getattr(title.render(), "plain", ""))
        scope = perm.query_one("#perm-scope")
        assert "all: bash" in str(getattr(scope.render(), "plain", ""))
        hint = perm.query_one("#perm-hint")
        assert "ctrl+f" in str(getattr(hint.render(), "plain", ""))
        perm._resolve("yes")
        await asyncio.wait_for(task, 2)


@pytest.mark.asyncio
async def test_focus_restored_after_answer(app):
    """§23: popup ditutup → fokus balik ke input."""
    async with app.run_test() as pilot:
        perm, task = await _open(app, pilot)
        assert isinstance(app.focused, type(perm.query_one("#perm-yes")))
        perm._resolve("yes")
        await asyncio.wait_for(task, 2)
        for _ in range(4):
            await pilot.pause()
        assert isinstance(app.focused, InputBar)


@pytest.mark.asyncio
async def test_policy_compat_no_session_approval(app):
    """Semantics checker utuh: run_python (NO_SESSION_APPROVAL) → tanpa All,
    scope 'sekali pakai'; bash biasa → All tampil."""
    async with app.run_test() as pilot:
        perm, task = await _open(app, pilot, "run_python",
                                 {"script": "print(1)"})
        assert perm.query_one("#perm-all").display is False
        scope = perm.query_one("#perm-scope")
        assert "sekali pakai" in str(getattr(scope.render(), "plain", ""))
        perm._resolve("yes")
        await asyncio.wait_for(task, 2)
        perm2, task2 = await _open(app, pilot, "bash", {"command": "ls"})
        assert perm2.query_one("#perm-all").display is True
        perm2._resolve("no")
        await asyncio.wait_for(task2, 2)


def test_scope_of():
    assert scope_of("bash", True) == "all: bash sisa session"
    assert scope_of("run_python", False) == "sekali pakai"
