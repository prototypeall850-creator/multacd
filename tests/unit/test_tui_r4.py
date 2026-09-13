"""Unit: selectors TUI-R4 — provider rows + status jujur (headless)."""

from __future__ import annotations

from tui.widgets.provider_selector import (
    ProviderSelector,
    build_rows,
    render_row,
)


def test_rows_grouped_empty_hidden():
    rows = build_rows([("groq", "Groq", True)], [("tavily", "Tavily", False)])
    assert [r[0] for r in rows] == ["head", "llm", "head", "search"]
    assert build_rows([], []) == []
    assert [r[0] for r in build_rows([], [("t", "T", True)])] == ["head", "search"]


def test_row_status_honest():
    assert "connected" in str(render_row(("llm", "groq", "Groq", True)))
    assert "belum" in str(render_row(("llm", "x", "X", False)))
    assert "aktif" in str(render_row(("search", "tavily", "Tavily", True)))
    head = render_row(("head", "Provider LLM"))
    assert "Provider LLM" in str(head) and "●" not in str(head)


def test_nav_skips_headers_unmounted():
    sel = ProviderSelector()
    sel.open([("groq", "Groq", True), ("custom", "Custom", False)],
             [("tavily", "Tavily", False)])
    assert sel.is_open and sel.selected == ("llm", "groq")
    sel.move(1)
    assert sel.selected == ("llm", "custom")
    sel.move(1)  # lompat header search
    assert sel.selected == ("search", "tavily")
    sel.move(-1)
    assert sel.selected == ("llm", "custom")
    sel.close()
    assert not sel.is_open and sel.selected is None
