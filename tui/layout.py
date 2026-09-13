"""Shell layout TUI-R1 — breakpoint murni, headless testable.

Aturan (TUI_REDESIGN.md §6):

    width >= 120  →  sidebar tampil, 24%
    width 90-119  →  sidebar tampil, 18%
    width < 90    →  sidebar hidden, chat 100%

Ctrl+I = manual override (None = ikut auto). Layar sempit (<70 kolom):
footer dipangkas (hints pendek). Tanpa import Textual — pure logic.
"""

from __future__ import annotations

from dataclasses import dataclass

SIDEBAR_WIDE = 120  # >= ini: sidebar lega
SIDEBAR_MIN = 90  # < ini: sidebar hidden (auto)
FOOTER_COMPACT = 70  # < ini: footer hints pendek
WIDE_PCT = "24%"
MID_PCT = "18%"
MANUAL_PCT = "45%"  # toggle manual di layar sempit: kasih ruang baca


@dataclass(frozen=True)
class ShellLayout:
    sidebar_visible: bool
    sidebar_width: str
    footer_compact: bool


def layout_for_width(width: int, manual: bool | None = None) -> ShellLayout:
    """Keputusan layout dari lebar terminal + override manual Ctrl+I.

    manual=None → ikut auto; True → paksa tampil; False → paksa hidden.
    Tak pernah raise; width aneh (<=0) = layar sempit.
    """
    try:
        w = int(width)
    except (TypeError, ValueError):
        w = 0
    auto_visible = w >= SIDEBAR_MIN
    auto_width = WIDE_PCT if w >= SIDEBAR_WIDE else MID_PCT
    if manual is None:
        visible, chosen = auto_visible, auto_width
    elif manual:
        # Manual tampil di layar sempit: kasih 45% biar kebaca.
        chosen = auto_width if auto_visible else MANUAL_PCT
        visible = True
    else:
        visible, chosen = False, auto_width
    return ShellLayout(
        sidebar_visible=visible,
        sidebar_width=chosen,
        footer_compact=w < FOOTER_COMPACT,
    )


if __name__ == "__main__":
    assert layout_for_width(160) == ShellLayout(True, "24%", False)
    assert layout_for_width(120) == ShellLayout(True, "24%", False)
    assert layout_for_width(119) == ShellLayout(True, "18%", False)
    assert layout_for_width(90) == ShellLayout(True, "18%", False)
    assert layout_for_width(89) == ShellLayout(False, "18%", False)
    assert layout_for_width(80) == ShellLayout(False, "18%", False)
    assert layout_for_width(60) == ShellLayout(False, "18%", True)
    assert layout_for_width(69).footer_compact is True
    assert layout_for_width(70).footer_compact is False
    # Manual override Ctrl+I.
    assert layout_for_width(160, False) == ShellLayout(False, "24%", False)
    assert layout_for_width(80, True) == ShellLayout(True, "45%", False)
    assert layout_for_width(160, True) == ShellLayout(True, "24%", False)
    assert layout_for_width(80, False) == ShellLayout(False, "18%", False)
    assert layout_for_width(0) == ShellLayout(False, "18%", True)
    assert layout_for_width(-5).sidebar_visible is False
    print("✅ layout self-test OK (breakpoint + override)")
