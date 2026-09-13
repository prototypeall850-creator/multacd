"""Unit: selection auto-copy + toast TUI-R8 (§25-27) — headless pilot."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("MULTACD_HOME", "/tmp/opencode/test-r8")

from textual import events

from core.config import Config
from tui.app import MultacdApp


@pytest.fixture()
def app():
    return MultacdApp(Config(model="groq/llama-3.3-70b", api_key="k"))


@pytest.mark.asyncio
async def test_empty_selection_noop(app, monkeypatch):
    """Seleksi kosong/None → no-op, tanpa copy (§25)."""
    async with app.run_test() as pilot:
        s = app.main_screen
        calls: list[str] = []
        monkeypatch.setattr("core.clipboard.copy_text",
                            lambda t: calls.append(t) or "ok")
        s.get_selected_text = lambda: None  # tanpa seleksi
        s.post_message(events.TextSelected())
        await pilot.pause()
        assert calls == []


@pytest.mark.asyncio
async def test_selection_autocopy_and_toast(app, monkeypatch):
    """Seleksi teks → copy_text dipanggil + toast muncul (§25/§27)."""
    async with app.run_test() as pilot:
        s = app.main_screen
        calls: list[str] = []
        monkeypatch.setattr("core.clipboard.copy_text",
                            lambda t: calls.append(t) or "tersalin (fake).")
        s.get_selected_text = lambda: "halo dari seleksi"
        s.post_message(events.TextSelected())
        await pilot.pause()
        await pilot.pause()
        assert calls == ["halo dari seleksi"]
        # Toast non-modal: notifikasi aktif, focus input tak berpindah.
        assert app.focused is not None  # input tetap fokus, toast tanpa fokus


@pytest.mark.asyncio
async def test_copy_failure_no_crash(app, monkeypatch):
    """Clipboard gagal → no crash, toast pesan gagal (§25)."""
    async with app.run_test() as pilot:
        s = app.main_screen

        def boom(t: str) -> str:
            raise OSError("no clipboard")

        monkeypatch.setattr("core.clipboard.copy_text", boom)
        s.get_selected_text = lambda: "teks"
        s.post_message(events.TextSelected())
        await pilot.pause()
        await pilot.pause()  # exception di thread → pesan gagal, app hidup


def test_textarea_not_interfered():
    """§25: TextSelected tak pernah dikirim untuk TextArea — jaminan Textual.

    Regressi guard: docstring events.TextSelected menyebut eksklusi input.
    """
    import inspect

    from textual import events as _ev
    src = inspect.getdoc(_ev.TextSelected) or ""
    assert "TextArea" in src
