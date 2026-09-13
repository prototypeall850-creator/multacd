"""Unit: command palette TUI-R3 — grup + overlay flag (headless)."""

from __future__ import annotations

from tui.widgets.slash_palette import (
    COMMAND_GROUPS,
    GROUP_OF,
    SlashPalette,
    grouped_matches,
    is_header,
)


def test_all_commands_grouped_once():
    from core.mode_manager import PALETTE_COMMANDS

    grouped = [c for _, cmds in COMMAND_GROUPS for c in cmds]
    assert sorted(grouped) == sorted(c for c, _ in PALETTE_COMMANDS)
    assert len(set(grouped)) == len(grouped) == 12


def test_grouped_structure_and_ranking():
    from core.mode_manager import PALETTE_COMMANDS

    g = grouped_matches("")
    headers = [c for c, _ in g if is_header((c, ""))]
    assert headers == ["##Mode", "##Model & provider", "##Sesi"]
    # Tiap grup: subset command existing, urutan ikut PALETTE_COMMANDS.
    order = [c for c, _ in PALETTE_COMMANDS]
    for grp, cmds in COMMAND_GROUPS:
        rows = [c for c, _ in g if GROUP_OF.get(c) == grp]
        assert rows == [c for c in order if c in cmds], (grp, rows)
    assert GROUP_OF["/model"] == "Model & provider"
    assert GROUP_OF["/clear"] == "Sesi"


def test_grouped_filter_hides_empty_groups():
    g = grouped_matches("mo")
    assert [c for c, _ in g] == ["##Model & provider", "/model", "/models"]
    assert grouped_matches("zzz") == []


def test_overlay_flag_lifecycle_unmounted():
    pal = SlashPalette()
    assert pal.overlay_open is False
    pal.open("", overlay=True)  # tanpa mount: _rebuild suppress, class ok
    assert pal.overlay_open is True
    assert pal.selected_command == "/code"  # header di-skip
    pal.move(3)  # /code → ... skip header, tetap command
    assert pal.selected_command is not None
    assert not is_header((pal._matches[pal._index][0], ""))
    pal.close()
    assert pal.overlay_open is False and pal._matches == []
