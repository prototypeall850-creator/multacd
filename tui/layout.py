"""Shell layout TUI-R1 — breakpoint murni, headless testable.

Aturan (TUI_REDESIGN_V2.md §9, TUI-R7 recompose):

    width >= 140  →  sidebar tampil, 24% (chat 76%)
    width 110-139 →  sidebar tampil, 18% (chat 82%)
    width < 110   →  sidebar hidden, chat 100%

Ctrl+I = manual override (None = ikut auto). Layar sempit (<70 kolom):
footer dipangkas (hints pendek). Input: base 1 baris konten + border,
tumbuh mengikuti multiline sampai cap (§16: jangan tinggi kalau 1 baris).
Tanpa import Textual — pure logic.
"""

from __future__ import annotations

from dataclasses import dataclass

SIDEBAR_WIDE = 140  # >= ini: sidebar lega
SIDEBAR_MIN = 110  # < ini: sidebar hidden (auto)
FOOTER_COMPACT = 100  # < ini: footer hints pendek (R12 §36: 80x24 minimal)
INPUT_COMPACT_ROWS = 30  # < ini: cap input pendek (kasih ruang chat di HP)
WIDE_PCT = "24%"
MID_PCT = "18%"
MANUAL_PCT = "45%"  # toggle manual di layar sempit: kasih ruang baca
INPUT_BORDER = 2  # border atas+bawah
INPUT_BASE_LINES = 1  # 1 baris konten saat kosong (§16)
INPUT_MAX_TALL = 8  # cap desktop: 6 baris konten
INPUT_MAX_SHORT = 5  # cap layar pendek: 3 baris konten


@dataclass(frozen=True)
class ShellLayout:
    sidebar_visible: bool
    sidebar_width: str
    footer_compact: bool
    input_base: int = INPUT_BASE_LINES + INPUT_BORDER  # 3
    input_max: int = INPUT_MAX_TALL


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
    max_h = (INPUT_MAX_SHORT if 0 < h < INPUT_COMPACT_ROWS
             else INPUT_MAX_TALL)
    return ShellLayout(
        sidebar_visible=visible,
        sidebar_width=chosen,
        footer_compact=w < FOOTER_COMPACT,
        input_base=INPUT_BASE_LINES + INPUT_BORDER,
        input_max=max_h,
    )


if __name__ == "__main__":
    assert layout_for_width(160) == ShellLayout(True, "24%", False, 3, 8)
    assert layout_for_width(140).sidebar_width == "24%"
    assert layout_for_width(139) == ShellLayout(True, "18%", False, 3, 8)
    assert layout_for_width(110).sidebar_visible is True
    assert layout_for_width(109) == ShellLayout(False, "18%", False, 3, 8)
    assert layout_for_width(80).sidebar_visible is False
    # R12 §36: <100 kolom footer pendek (80x24 → 1 baris, tak wrap).
    assert layout_for_width(80).footer_compact is True
    assert layout_for_width(99).footer_compact is True
    assert layout_for_width(100).footer_compact is False
    assert layout_for_width(60).footer_compact is True
    # Manual override Ctrl+I.
    assert layout_for_width(160, False) == ShellLayout(False, "24%", False, 3, 8)
    assert layout_for_width(80, True) == ShellLayout(True, "45%", True, 3, 8)
    assert layout_for_width(160, True).sidebar_width == "24%"
    assert layout_for_width(80, False).sidebar_visible is False
    assert layout_for_width(0) == ShellLayout(False, "18%", True, 3, 8)
    assert layout_for_width(-5).sidebar_visible is False
    # TUI-R7: input base 3; cap 8 desktop, 5 di layar pendek (<30 baris).
    assert layout_for_width(120, None, 40).input_max == 8
    assert layout_for_width(120, None, 30).input_max == 8
    assert layout_for_width(80, None, 29).input_max == 5
    assert layout_for_width(80, None, 24).input_max == 5
    assert layout_for_width(80, None, 0).input_max == 8  # unknown = aman
    print("✅ layout self-test OK (breakpoint + override + input grow)")
