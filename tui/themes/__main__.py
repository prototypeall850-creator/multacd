"""Self-test themes (python -m tui.themes)."""

from tui.themes import (
    DEFAULT_THEME,
    THEMES,
    resolve_theme_name,
)

assert len(THEMES) == 7  # 4 catppuccin kompat + 3 multacd v2
assert DEFAULT_THEME == "multacd-dark"
assert resolve_theme_name("dark") == "multacd-dark"
assert resolve_theme_name("LIGHT") == "multacd-light"
assert resolve_theme_name("catppuccin-mocha") == "catppuccin-mocha"
assert resolve_theme_name("frappe-typo") == DEFAULT_THEME
latte = next(t for t in THEMES if t.name == "catppuccin-latte")
mocha = next(t for t in THEMES if t.name == "catppuccin-mocha")
assert not latte.dark and mocha.dark
mdark = next(t for t in THEMES if t.name == "multacd-dark")
mmin = next(t for t in THEMES if t.name == "multacd-min")
assert mdark.dark and mmin.dark
# Token semantik wajib ada di semua varian (anti dead-token lagi).
for _t in THEMES:
    for _k in ("subtext", "overlay", "peach", "teal", "sapphire",
               "lavender", "success-dim"):
        assert _k in _t.variables, (_t.name, _k)
print("✅ themes self-test OK (7 varian + alias v2)")
