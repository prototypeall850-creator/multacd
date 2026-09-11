"""Design tokens multacd v2 — lapisan semantik di atas hex mentah.

Kenapa ada: theme lama (Catppuccin mentah) dipakai langsung sebagai
hex di widget, jadi ganti theme tidak ngaruh + dead token
(peach/teal/sapphire/lavender tak dipakai). Di sini widget pakai
nama semantik, theme tinggal mapping.

    from tui.tokens import is_min_mode, should_animate, narrow
"""

from __future__ import annotations

import os
import shutil


def term_width(default: int = 80) -> int:
    """Lebar terminal, fallback aman buat test/CI."""
    try:
        return shutil.get_terminal_size((default, 24)).columns or default
    except Exception:
        return default


def narrow(cols: int | None = None) -> bool:
    """True kalau layar HP/sempit (<70 kolom). Panel kanan wajib overlay."""
    w = cols if cols is not None else term_width()
    return w < 70


def is_min_mode() -> bool:
    """Mode hemat Termux: ascii + tanpa animasi + watcher jarang.

    Trigger (salah satu cukup):
    - MULTACD_MIN=1 / MULTACD_NO_ANIM=1
    - NO_COLOR / NO_EMOJI ter-set
    - TERMUX_VERSION terdeteksi + COLUMNS < 70
    """
    env = os.environ
    if env.get("MULTACD_MIN", "") == "1" or env.get("MULTACD_NO_ANIM", "") == "1":
        return True
    if env.get("NO_COLOR") is not None or env.get("NO_EMOJI") is not None:
        return True
    if "TERMUX_VERSION" in env:
        try:
            if int(env.get("COLUMNS", "80") or 80) < 70:
                return True
        except ValueError:
            return True
    return False


def should_animate() -> bool:
    """Animasi thinking jalan kecuali min-mode."""
    return not is_min_mode()


# Nama semantik → slot Textual Theme (bukan hex, biar ganti theme ngaruh).
SEMANTIC = {
    "bg": "background",
    "card": "surface",
    "deep": "panel",
    "hover": "boost",
    "text": "foreground",
    "muted": "subtext",  # var(--subtext)
    "faint": "overlay",  # var(--overlay)
    "ok": "success",
    "warn": "warning",
    "err": "error",
    "run": "sapphire",  # var(--sapphire)
    "accent": "accent",
    "info": "primary",
    "hl": "lavender",  # var(--lavender)
    "git_mod": "peach",  # var(--peach)
    "git_new": "teal",  # var(--teal)
}

# Mode → token semantik (single source, ganti di sini saja).
MODE_TOKEN = {"code": "ok", "research": "info", "personal": "accent"}


if __name__ == "__main__":
    assert narrow(40) is True and narrow(100) is False
    os.environ["MULTACD_MIN"] = "1"
    try:
        assert is_min_mode() and not should_animate()
    finally:
        del os.environ["MULTACD_MIN"]
    assert SEMANTIC["run"] == "sapphire" and MODE_TOKEN["code"] == "ok"
    print("✅ tokens self-test OK")
