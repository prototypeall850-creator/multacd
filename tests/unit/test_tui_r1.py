"""Unit: shell TUI-R1 — layout breakpoint + bar/sidebar/footer (headless)."""

from __future__ import annotations

from tui.layout import ShellLayout, layout_for_width
from tui.widgets.context_sidebar import get_mcp_servers, render_mcp
from tui.widgets.footer_bar import render_footer, short_workdir
from tui.widgets.session_bar import render_session_title


def test_breakpoints_brief():
    assert layout_for_width(160) == ShellLayout(True, "24%", False, 5)
    assert layout_for_width(120).sidebar_width == "24%"
    assert layout_for_width(119) == ShellLayout(True, "18%", False, 5)
    assert layout_for_width(90).sidebar_visible is True
    assert layout_for_width(89) == ShellLayout(False, "18%", False, 5)
    assert layout_for_width(80).sidebar_visible is False


def test_manual_override_ctrl_i():
    assert layout_for_width(160, False).sidebar_visible is False
    assert layout_for_width(80, True) == ShellLayout(True, "45%", False, 5)
    assert layout_for_width(160, True).sidebar_width == "24%"
    assert layout_for_width(80, False).sidebar_visible is False
    assert layout_for_width(80, None).sidebar_visible is False


def test_input_height_short_screens():
    assert layout_for_width(120, None, 40).input_height == 5
    assert layout_for_width(120, None, 30).input_height == 5
    assert layout_for_width(80, None, 29).input_height == 3
    assert layout_for_width(80, None, 24).input_height == 3
    assert layout_for_width(80, True, 24) == ShellLayout(True, "45%", False, 3)


def test_footer_compact_narrow():
    assert layout_for_width(69).footer_compact is True
    assert layout_for_width(70).footer_compact is False


def test_session_title_single():
    assert render_session_title("myapp") == "myapp"
    assert render_session_title("") == "—"
    assert render_session_title("  ") == "—"


def test_footer_render_no_fake():
    assert "ctrl+i panel" in render_footer("~/p", "— · —", False)
    assert "ctrl+i panel" not in render_footer("~/p", "— · —", True)
    assert "—" in render_footer("~/p", "", False)  # usage kosong = jujur


def test_short_workdir():
    from pathlib import Path

    home = str(Path.home())
    assert short_workdir(home) == "~"
    assert short_workdir(f"{home}/proj") == "~/proj"
    assert short_workdir("") == "?"
    chopped = short_workdir("/a/" + "x" * 60, 32)
    assert len(chopped) == 32 and chopped.startswith("…")


def test_mcp_empty_honest():
    assert get_mcp_servers() == []
    assert render_mcp([]) == "MCP\n—"
    s = render_mcp([{"name": "figma", "status": "Connected"}])
    assert "● figma" in s and "Connected" in s


def test_widgets_no_crash_unmounted():
    from tui.widgets.context_sidebar import ContextSidebar
    from tui.widgets.footer_bar import FooterBar
    from tui.widgets.session_bar import SessionBar

    bar = SessionBar.__new__(SessionBar)
    bar._title = ""
    SessionBar.set_title(bar, "myapp")
    assert bar._title == "myapp"

    foot = FooterBar.__new__(FooterBar)
    foot._workdir, foot._usage, foot._compact = "?", "—", False
    FooterBar.set_data(foot, "~/p", "1 · —")
    FooterBar.set_compact(foot, True)
    assert foot._compact is True

    side = ContextSidebar.__new__(ContextSidebar)
    side.set_mcp([])  # suppress: tanpa mount tak crash
