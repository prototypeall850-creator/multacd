"""Unit: final polish TUI-R12 — footer breakpoint, theme color, palette."""

from __future__ import annotations

from tui.layout import layout_for_width
from tui.tokens import rich_color


def test_footer_compact_breakpoint():
    """§36: 80x24 footer 1 baris (hints pendek); desktop hints penuh."""
    assert layout_for_width(80).footer_compact is True
    assert layout_for_width(99).footer_compact is True
    assert layout_for_width(100).footer_compact is False
    assert layout_for_width(120).footer_compact is False


def test_sidebar_breakpoints_brief_matrix():
    """§36: 80/100 hidden, 120/140/160 visible."""
    assert [layout_for_width(w).sidebar_visible
            for w in (80, 100, 120, 140, 160)] == \
        [False, False, True, True, True]
    assert layout_for_width(160).sidebar_width == "24%"
    assert layout_for_width(120).sidebar_width == "18%"


def test_rich_color_from_theme_and_fallback():
    """rich_color: theme aktif menang; tanpa app → hex fallback."""
    class FakeApp:
        def get_css_variables(self):
            return {"peach": "#00ff00"}
    assert rich_color(FakeApp(), "peach", "#fab387") == "#00ff00"
    assert rich_color(FakeApp(), "nope", "#fab387") == "#fab387"  # var tak ada
    assert rich_color(None, "peach", "#fab387") == "#fab387"      # no app
    assert rich_color(object(), "peach", "#fab387") == "#fab387"  # tak punya api


def test_render_item_accent_param():
    """render_item pure + accent param (theme via caller)."""
    from tui.widgets.slash_palette import render_item
    t = render_item("/model", "Switch", "mo", accent="#ff0000")
    assert "/model" in t.plain
    assert any(s.style and "bold" in str(s.style) and "#ff0000" in str(s.style)
               for s in t.spans if s.style)
