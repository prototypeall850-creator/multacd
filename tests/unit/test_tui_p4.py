"""Unit: P4 slash palette inline ala opencode — flat ranked + dua kolom."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("MULTACD_HOME", "/tmp/opencode/test-p4")

from core.config import Config
from tui.app import MultacdApp
from tui.widgets.slash_palette import (
    HEADER_MARK,
    SlashPalette,
    is_header,
    render_item,
)


def test_render_item_two_columns():
    t = render_item("/model", "Switch model", "mo", width=60)
    plain = t.plain
    assert plain.startswith("/model")
    col = max(14, min(60 - 24, 40))  # 36
    assert plain.index("Switch model") == col


def test_render_item_desc_truncated():
    t = render_item("/x", "A" * 200, "", width=60)
    assert t.plain.rstrip().endswith("…")
    assert len(t.plain) <= 60


def test_render_item_shortcut_keeps_column():
    a = render_item("/model", "Ganti", "mo", width=60).plain
    b = render_item("/models", "Ganti", "", width=60).plain  # punya ctrl+o
    assert a.index("Ganti") == b.index("Ganti")  # kolom rata walau shortcut


def test_inline_flat_overlay_grouped():
    pal = SlashPalette()
    pal.open("mo", overlay=False)
    assert pal._matches and not any(is_header(m) for m in pal._matches)
    pal.open("mo", overlay=True)
    assert any(m[0].startswith(HEADER_MARK) for m in pal._matches)


@pytest.fixture()
def app():
    return MultacdApp(Config(model="groq/llama-3.3-70b", api_key="k"))


@pytest.mark.asyncio
async def test_inline_palette_no_title_columns(app):
    """Ketik '/' → palette inline: tanpa judul 'commands', dua kolom rata."""
    from textual.widgets import Label

    from core.mode_manager import PALETTE_COMMANDS

    async with app.run_test(size=(100, 30)) as pilot:
        await app.pop_screen()  # tutup FreshScreen
        for _ in range(3):
            await pilot.pause()
        s = app.main_screen
        title = s.query_one("#slash-title")
        inp = s.query_one("#input-bar")
        inp.text = "/"
        for _ in range(4):
            await pilot.pause()
        pal = s.query_one("#slash-palette")
        assert pal.display
        assert title.display is False  # P4: opencode tanpa judul inline
        label = pal.query(Label).first()
        text = label.render().plain
        cmd = text.split()[0]
        desc = dict(PALETTE_COMMANDS)[cmd]
        col = max(14, min(pal._content_width() - 24, 40))
        head = desc.split()[0]
        assert head in text[col - 1:]  # rata kolom, bukan nempel nama
