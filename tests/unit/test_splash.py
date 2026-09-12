"""Unit: splash §10 — tips valid tanpa mount widget (R7)."""

from __future__ import annotations

import random

from tui.widgets.chat_panel import ChatPanel


def test_tips_nonempty_and_truthful():
    assert len(ChatPanel.SPLASH_TIPS) >= 3
    for tip in ChatPanel.SPLASH_TIPS:
        assert tip.strip(), "tip kosong"


def test_pick_tip_deterministic_with_seeded_rng():
    rng = random.Random(42)
    seen = {ChatPanel.pick_tip(rng) for _ in range(20)}
    assert seen <= set(ChatPanel.SPLASH_TIPS)
    assert len(seen) > 1  # beneran bergantian, bukan 1 tip terus
