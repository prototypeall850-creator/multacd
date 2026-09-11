"""Unit: entry point — app(), versi konsisten, console script."""

from __future__ import annotations

import shutil

import pytest


def test_app_entry_calls_main(monkeypatch):
    import main as _main

    seen: dict = {}

    def _fake(argv=None):
        seen["argv"] = argv
        return 0

    monkeypatch.setattr(_main, "main", _fake)
    with pytest.raises(SystemExit) as e:
        _main.app()
    assert e.value.code == 0 and seen == {"argv": None}


def test_version_single_source():
    from core.updater import FALLBACK_VERSION
    from core.version import FALLBACK, get_version
    from tui.app import APP_VERSION

    assert FALLBACK_VERSION == FALLBACK
    assert get_version() == APP_VERSION


def test_console_script_version():
    """`multacd --version` jalan (skip kalau belum pip install -e .)."""
    import subprocess as _sp
    import sys
    from pathlib import Path

    from core.version import get_version

    exe = shutil.which("multacd")
    if exe is None:  # fallback: script di venv yang sama
        candidate = Path(sys.executable).parent / "multacd"
        exe = str(candidate) if candidate.is_file() else None
    if exe is None:
        pytest.skip("console script belum terinstall (pip install -e . dulu)")
    proc = _sp.run([exe, "--version"], capture_output=True, text=True,
                   timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert get_version() in proc.stdout
