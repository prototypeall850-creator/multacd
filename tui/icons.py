"""Icon system 3 level (lihat DESIGN.md §1).

nerdfonts → unicode → ascii, dengan deteksi otomatis + override config.

    from tui import icons
    icons.setup("auto")     # sekali saat startup
    icons.icon("success")   # glyph sesuai level aktif

Level auto: ascii kalau TERM=dumb atau stdout bukan UTF-8, selain itu
unicode. Nerd Fonts = opt-in via config (icon_style: nerdfonts).

NOTE jujur: DESIGN minta probe render-width terminal buat deteksi Nerd
Fonts otomatis. Itu butuh roundtrip query ke terminal yang tidak bisa
diandalkan dari dalam Textual — jadi auto tidak pernah menebak
nerdfonts sendiri. Lihat issue fase DESIGN.
"""

from __future__ import annotations

import locale
import os

LEVELS = ("nerdfonts", "unicode", "ascii")

# glyph per level: (nerdfonts, unicode, ascii)
_ICONS: dict[str, tuple[str, str, str]] = {
    "app": ("\uf0e7", "*", "[*]"),             # fa-bolt (nerd); tenang di semua level
    "mode": ("\uf108", ">", "[>]"),          # fa-desktop
    "folder": ("\uf07b", "*", "[+]"),
    "file": ("\uf15b", "-", "--"),
    "python": ("\ue73c", "~", "(py)"),
    "branch": ("\ue0a0", "@", "(br)"),
    "search": ("", ">", ">>"),
    "terminal": ("", ">", "$"),
    "settings": ("", "#", "[=]"),
    "success": ("", "*", "[OK]"),
    "error": ("", "x", "[!!]"),
    "warning": ("", "!", "[!]"),
    "pending": ("…", "..", "[..]"),
    "running": ("\uf054", ">", ">>"),
    "modified": ("●", "+", "[M]"),
    "added": ("\uf067", "+", "[A]"),
    "deleted": ("\uf068", "-", "[D]"),
    "renamed": ("→", ">", "[R]"),
    "conflict": ("\uf071", "!", "[C]"),      # fa-warning, bukan emoji ⚠
    "expand": ("[+]", "[+]", "[+]"),
    "collapse": ("[-]", "[-]", "[-]"),
    "bullet": ("•", "*", "*"),
    "arrow": ("→", ">", ">"),
    "export": ("\uf019", "#", "[E]"),        # fa-download, bukan ⭳
    "preview": ("\uf06e", "@", "[?]"),       # fa-eye, bukan emoji 👁
}

_level: str = "unicode"


def detect_level() -> str:
    """Auto: ascii kalau terminal terbatas, else unicode.

    v2: hormati NO_EMOJI/NO_COLOR/TERMUX sempit → ascii (jalur utama HP).
    Nerd Fonts tetap opt-in via config (probe render tak andal di Textual).
    """
    if os.environ.get("TERM") == "dumb":
        return "ascii"
    if os.environ.get("NO_EMOJI") is not None or os.environ.get("NO_COLOR") is not None:
        return "ascii"
    if "TERMUX_VERSION" in os.environ:
        try:
            cols = int(os.environ.get("COLUMNS", "80") or 80)
        except ValueError:
            cols = 80
        if cols < 70 or os.environ.get("MULTACD_MIN") == "1":
            return "ascii"
    enc = (locale.getpreferredencoding(False) or "").lower()
    if "utf" not in enc:
        return "ascii"
    return "unicode"


def setup(style: str = "auto") -> str:
    """Pilih level aktif. Return level yang dipakai."""
    global _level
    style = (style or "auto").lower().strip()
    if style in LEVELS:
        _level = style
    elif style == "auto":
        _level = detect_level()
    else:
        _level = "unicode"
    return _level


def icon(name: str) -> str:
    """Glyph untuk nama ikon. Tidak dikenal → nama itu sendiri."""
    _tri = _ICONS.get(name)
    if _tri is None:
        return name
    idx = LEVELS.index(_level)
    return _tri[idx]


def active_level() -> str:
    return _level


if __name__ == "__main__":
    # Tabel lengkap: tiap nama punya 3 glyph non-kosong.
    for _name, _tri in _ICONS.items():
        assert len(_tri) == 3 and all(_tri), _name

    assert setup("ascii") == "ascii" and icon("success") == "[OK]"
    assert setup("nerdfonts") == "nerdfonts" and icon("folder") == "\uf07b"
    assert setup("ngawur") == "unicode"  # fallback aman

    # Auto: TERM=dumb → ascii
    _old = os.environ.get("TERM")
    os.environ["TERM"] = "dumb"
    try:
        assert setup("auto") == "ascii"
    finally:
        if _old is None:
            del os.environ["TERM"]
        else:
            os.environ["TERM"] = _old
    # v2: NO_EMOJI / Termux sempit → ascii
    os.environ["NO_EMOJI"] = "1"
    try:
        assert setup("auto") == "ascii"
    finally:
        del os.environ["NO_EMOJI"]
    assert setup("auto") == detect_level() and active_level() in LEVELS
    assert icon("tidak-ada") == "tidak-ada"  # unknown → passthrough
    print("✅ icons self-test OK (tabel + setup + auto)")
