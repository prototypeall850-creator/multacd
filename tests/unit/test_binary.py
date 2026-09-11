"""Guard binary (Phase 5 Step 5) — spec valid + artifact jalan.

Build penuh (`pyinstaller multacd.spec`) hanya di lokal/CI, bukan di pytest.
Test ini: spec compile, entry/data lengkap, dan kalau dist/ ada,
`multacd --version` benar-benar jalan.
"""

from __future__ import annotations

import subprocess as _sp
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SPEC = ROOT / "multacd.spec"
DIST = ROOT / "dist" / "multacd"


def test_spec_compiles():
    src = SPEC.read_text(encoding="utf-8")
    compile(src, str(SPEC), "exec")


def test_spec_has_entry_and_data():
    src = SPEC.read_text(encoding="utf-8")
    assert '"main.py"' in src
    assert "soul.md" in src
    assert "console=True" in src
    assert "onefile=True" in src
    assert "litellm" in src and "tiktoken" in src


def test_dist_binary_version():
    if not (DIST.is_file() and DIST.stat().st_mode & 0o111):
        pytest.skip("dist/multacd belum dibuild (pyinstaller multacd.spec dulu)")
    from core.version import get_version

    proc = _sp.run([str(DIST), "--version"], capture_output=True, text=True,
                   timeout=180)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert get_version() in proc.stdout
