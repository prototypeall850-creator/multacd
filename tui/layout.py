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
INPUT_COMPACT_ROWS = 30  # < ini: input 3 baris (kasih ruang chat di HP)
WIDE_PCT = "24%"
MID_PCT = "18%"
MANUAL_PCT = "45%"  # toggle manual di layar sempit: kasih ruang baca
INPUT_TALL = 5
INPUT_SHORT = 3


@dataclass(frozen=True)
class ShellLayout:
    sidebar_visible: bool
    sidebar_width: str
    footer_compact: bool
    input_height: int = INPUT_TALL


def layout_for_width(width: int, manual: bool | None = None,
                     height: int = 40) -> ShellLayout:
    """Keputusan layout dari lebar + tinggi terminal + override manual.

    manual=None → ikut auto; True → paksa tampil; False → paksa hidden.
    Tak pernah raise; width/height aneh (<=0) = layar sempit.
    """
    try:
        w = int(width)
    except (TypeError, ValueError):
        w = 0
    try:
        h = int(height)
    except (TypeError, ValueError):
        h = 0
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
        input_height=INPUT_SHORT if 0 < h < INPUT_COMPACT_ROWS else INPUT_TALL,
    )


if __name__ == "__main__":
    assert layout_for_width(160) == ShellLayout(True, "24%", False, 5)
    assert layout_for_width(120) == ShellLayout(True, "24%", False, 5)
    assert layout_for_width(119) == ShellLayout(True, "18%", False, 5)
    assert layout_for_width(90) == ShellLayout(True, "18%", False, 5)
    assert layout_for_width(89) == ShellLayout(False, "18%", False, 5)
    assert layout_for_width(80) == ShellLayout(False, "18%", False, 5)
    assert layout_for_width(60) == ShellLayout(False, "18%", True, 5)
    assert layout_for_width(69).footer_compact is True
    assert layout_for_width(70).footer_compact is False
    # Manual override Ctrl+I.
    assert layout_for_width(160, False) == ShellLayout(False, "24%", False, 5)
    assert layout_for_width(80, True) == ShellLayout(True, "45%", False, 5)
    assert layout_for_width(160, True) == ShellLayout(True, "24%", False, 5)
    assert layout_for_width(80, False) == ShellLayout(False, "18%", False, 5)
    assert layout_for_width(0) == ShellLayout(False, "18%", True, 5)
    assert layout_for_width(-5).sidebar_visible is False
    # TUI-R6: input pendek di layar pendek (<30 baris).
    assert layout_for_width(120, None, 40).input_height == 5
    assert layout_for_width(120, None, 30).input_height == 5
    assert layout_for_width(80, None, 24).input_height == 3
    assert layout_for_width(80, None, 29).input_height == 3
    assert layout_for_width(80, None, 0).input_height == 5  # unknown = aman
    print("✅ layout self-test OK (breakpoint + override + input)")
