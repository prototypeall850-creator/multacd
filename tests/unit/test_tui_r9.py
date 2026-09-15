"""Unit: tool activity TUI-R9 (§14-15) — state glyph + shell body (headless)."""

from __future__ import annotations

from textual.content import Content

from tui.widgets.tool_activity import (
    body_text,
    head_markup,
    state_glyph,
    summarize,
)


def test_state_glyphs_five_states():
    """§14: → running · ✓ done · x failed · ↗ background · ■ cancelled."""
    glyphs = {st: state_glyph(st) for st in
              ("running", "done", "failed", "background", "cancelled")}
    assert all(glyphs.values()), glyphs
    assert len(set(glyphs.values())) == 5  # beda state = beda glyph
    assert state_glyph("ngawur") == ""


def test_header_markup_valid_all_states():
    """Header tak pernah crash markup (issue #29), semua state."""
    nasty = 'ls [a-z]* [x=y="cmd", z]'
    for done, ok in ((False, False), (True, True), (True, False)):
        Content.from_markup(head_markup("bash", nasty, done, ok))


def test_cancelled_head_warning_token_not_red():
    """m-C (ronde-2 audit): cancelled = kuning token `warning`
    (DESIGN.md:134, #f9e2af), bukan [red] — resolve dari theme aktif
    (pattern tokens: single source), markup tetap valid."""
    c = head_markup("bash", "x", False, False, cancelled=True)
    assert "[$warning]" in c, c
    assert "[red]" not in c and "[yellow]" not in c, c
    Content.from_markup(c)


def test_shell_body_command_prefix():
    """§15: shell expanded → `$ pytest tests/` dulu, baru output."""
    s, d = summarize({"success": True, "result": "3 passed in 2s",
                      "error": None})
    body = body_text(s, d, command="pytest tests/")
    plain = body.plain
    assert plain.startswith("$ pytest tests/"), plain
    assert "3 passed in 2s" in plain


def test_nonsheel_body_tanpa_prefix():
    """Tool non-shell (read_file dkk) → tanpa `$`."""
    body = body_text("Created file (3 lines)", "", command="")
    assert "$" not in body.plain and "Created" in body.plain
