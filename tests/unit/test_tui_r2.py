"""Unit: chat visual TUI-R2 — meta murni + kontrak close (headless)."""

from __future__ import annotations

from tui.widgets.chat_panel import render_meta


def test_meta_full_with_usage():
    m = render_meta("code", "groq/llama-3.3-70b", 4.7, 475)
    assert m == "code · llama-3.3-70b · 4.7s · 101 tok/s", m


def test_meta_no_usage_no_fake_rate():
    m = render_meta("code", "custom/model", 3.2, 0)
    assert m == "code · model · 3.2s", m
    assert "tok/s" not in m


def test_meta_model_short_and_mode():
    m = render_meta("research", "x", 0.0, 0)
    assert m.startswith("research · x · 0.0s"), m
    long_m = render_meta("code", "prov/" + "n" * 50, 1.0, 0)
    assert len("prov/" + "n" * 50) > 28
    assert "n" * 50 not in long_m  # dipotong 28 char
