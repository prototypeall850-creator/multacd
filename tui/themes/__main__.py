"""Self-test themes (python -m tui.themes)."""

from tui.themes import (
    DEFAULT_THEME,
    THEMES,
    resolve_theme_name,
)

assert len(THEMES) == 4
assert all(t.name.startswith("catppuccin-") for t in THEMES)
assert resolve_theme_name("dark") == "catppuccin-mocha"
assert resolve_theme_name("LIGHT") == "catppuccin-latte"
assert resolve_theme_name("frappe-typo") == DEFAULT_THEME
latte = next(t for t in THEMES if t.name == "catppuccin-latte")
mocha = next(t for t in THEMES if t.name == "catppuccin-mocha")
assert not latte.dark and mocha.dark
print("✅ catppuccin self-test OK (4 varian + alias)")
