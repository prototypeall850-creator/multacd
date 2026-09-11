"""multacd themes v2 — identitas sendiri + Catppuccin kompatibel.

Default: multacd-dark (turunan Mocha, aksen sapphire khas + kontras
dinaikkan buat layar HP). Varian: multacd-light, multacd-min
(16 warna sistem buat Termux hemat). 4 Catppuccin lama tetap ada
biar config v1 tidak crash — full bebas tapi config lama kebaca.
"""

from __future__ import annotations

from textual.theme import Theme

MOCHA = Theme(
    name="catppuccin-mocha",
    dark=True,
    primary="#89b4fa",      # Blue — info, link
    secondary="#94e2d5",    # Teal — git new
    accent="#cba6f7",       # Mauve — accent, /personal
    foreground="#cdd6f4",   # Text
    background="#1e1e2e",   # Base
    surface="#313244",      # Surface 0
    panel="#181825",        # Mantle
    success="#a6e3a1",      # Green
    warning="#f9e2af",      # Yellow
    error="#f38ba8",        # Red
    boost="#45475a",        # Surface 1 — hover/selected
    variables={
        "subtext": "#a6adc8",
        "overlay": "#7f849c",
        "peach": "#fab387",      # git modified
        "teal": "#94e2d5",       # git new
        "sapphire": "#74c7ec",   # tool running
        "lavender": "#b4befe",   # highlight
        "success-dim": "#585b70",
    },
)

LATTE = Theme(
    name="catppuccin-latte",
    dark=False,
    primary="#1e66f5",
    secondary="#179299",
    accent="#8839ef",
    foreground="#4c4f69",
    background="#eff1f5",
    surface="#ccd0da",
    panel="#e6e9ef",
    success="#40a02b",
    warning="#df8e1d",
    error="#d20f39",
    boost="#bcc0cc",
    variables={
        "subtext": "#6c6f85",
        "overlay": "#9ca0b0",
        "peach": "#fe640b",
        "teal": "#179299",
        "sapphire": "#209fb5",
        "lavender": "#7287fd",
        "success-dim": "#acb0be",
    },
)

FRAPPE = Theme(
    name="catppuccin-frappe",
    dark=True,
    primary="#8caaee",
    secondary="#81c8be",
    accent="#ca9ee6",
    foreground="#c6d0f5",
    background="#303446",
    surface="#414559",
    panel="#292c3c",
    success="#a6d189",
    warning="#e5c890",
    error="#e78284",
    boost="#51576d",
    variables={
        "subtext": "#a5adce",
        "overlay": "#838ba7",
        "peach": "#ef9f76",
        "teal": "#81c8be",
        "sapphire": "#85c1dc",
        "lavender": "#babbf1",
        "success-dim": "#626880",
    },
)

MACCHIATO = Theme(
    name="catppuccin-macchiato",
    dark=True,
    primary="#8aadf4",
    secondary="#8bd5ca",
    accent="#c6a0f6",
    foreground="#cad3f5",
    background="#24273a",
    surface="#363a4f",
    panel="#1e2030",
    success="#a6da95",
    warning="#eed49f",
    error="#ed8796",
    boost="#494d64",
    variables={
        "subtext": "#a5adcb",
        "overlay": "#8087a2",
        "peach": "#f5a97f",
        "teal": "#8bd5ca",
        "sapphire": "#7dc4e4",
        "lavender": "#b7bdf8",
        "success-dim": "#5b6078",
    },
)

MULTACD_DARK = Theme(
    name="multacd-dark",
    dark=True,
    primary="#74c7ec",      # Sapphire khas — beda dari Catppuccin Blue
    secondary="#94e2d5",    # Teal
    accent="#cba6f7",       # Mauve
    foreground="#dbe1f5",   # Text Mocha + kontras naik (HP)
    background="#16161f",   # Base lebih pekat dari Mocha
    surface="#262633",      # card
    panel="#101016",        # deep
    success="#a6e3a1",
    warning="#f9e2af",
    error="#f38ba8",
    boost="#3a3a4d",
    variables={
        "subtext": "#b4bad6",  # dinaikkan (Overlay lama kelewat redup di HP)
        "overlay": "#8b91a8",
        "peach": "#fab387",
        "teal": "#94e2d5",
        "sapphire": "#74c7ec",
        "lavender": "#b4befe",
        "success-dim": "#585b70",
    },
)

MULTACD_LIGHT = Theme(
    name="multacd-light",
    dark=False,
    primary="#209fb5",
    secondary="#179299",
    accent="#8839ef",
    foreground="#3a3d55",   # lebih pekat dari Latte
    background="#f2f3f7",
    surface="#d8dbe4",
    panel="#e8eaf0",
    success="#328a24",
    warning="#c7740a",
    error="#c20f33",
    boost="#c2c6d2",
    variables={
        "subtext": "#5c5f77",
        "overlay": "#8a8da0",
        "peach": "#e85a0c",
        "teal": "#179299",
        "sapphire": "#209fb5",
        "lavender": "#5a6cf5",
        "success-dim": "#acb0be",
    },
)

MULTACD_MIN = Theme(
    name="multacd-min",
    dark=True,
    # 16 warna sistem — aman di Termux tanpa truecolor, tanpa animasi.
    primary="cyan",
    secondary="cyan",
    accent="magenta",
    foreground="white",
    background="black",
    surface="black",
    panel="black",
    success="green",
    warning="yellow",
    error="red",
    boost="black",
    variables={
        "subtext": "white",
        "overlay": "white",
        "peach": "yellow",
        "teal": "cyan",
        "sapphire": "cyan",
        "lavender": "white",
        "success-dim": "white",
    },
)

THEMES = (MOCHA, LATTE, FRAPPE, MACCHIATO, MULTACD_DARK, MULTACD_LIGHT, MULTACD_MIN)
DEFAULT_THEME = "multacd-dark"

# Alias kompatibel config lama (dark/light era Phase 2) + v1 catppuccin.
# Full bebas v2: default pindah ke identitas sendiri, catppuccin tetap bisa dipilih.
THEME_ALIASES = {
    "dark": "multacd-dark",
    "light": "multacd-light",
    "catppuccin": "catppuccin-mocha",
    "mocha": "catppuccin-mocha",
    "latte": "catppuccin-latte",
}


def resolve_theme_name(name: str) -> str:
    """'dark' → 'multacd-dark', dst. Tidak dikenal → default."""
    name = (name or "").lower().strip()
    if name in THEME_ALIASES:
        return THEME_ALIASES[name]
    if any(t.name == name for t in THEMES):
        return name
    return DEFAULT_THEME
