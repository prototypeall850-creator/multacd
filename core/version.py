"""Single source versi runtime (Phase 5 Step 4).

    pyproject.toml  → versi resmi (dipakai metadata saat pip install)
    get_version()   → metadata kalau terinstall, else FALLBACK (source checkout)

Saat bump versi (Step 10 → 1.0.0): ubah pyproject + FALLBACK di sini.
"""

from __future__ import annotations

FALLBACK = "2.0.0b5"  # beta v2; samakan dengan pyproject.toml


def get_version() -> str:
    """Versi terinstall, atau fallback kalau jalan dari source checkout."""
    try:
        from importlib.metadata import version
        return version("multacd")
    except Exception:
        return FALLBACK
