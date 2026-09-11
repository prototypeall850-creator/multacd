"""Test installer scripts (Phase 5 Step 6) — tanpa sentuh network asli."""

from __future__ import annotations

import functools
import http.server
import os
import stat
import subprocess as _sp
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SH = ROOT / "scripts" / "install.sh"
INSTALL_PS1 = ROOT / "scripts" / "install.ps1"

needs_posix = pytest.mark.skipif(os.name == "nt", reason="butuh bash/unix")


def _run(cmd: list[str], **kw) -> _sp.CompletedProcess:
    return _sp.run(cmd, capture_output=True, text=True, timeout=120, **kw)


def _source_detect(uname_s: str, uname_m: str, tmp_path: Path) -> str:
    """Jalankan detect_platform dengan stub uname (tanpa eksekusi main)."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    stub = bindir / "uname"
    stub.write_text(f'#!/usr/bin/env bash\nif [ "$1" = "-s" ]; then echo "{uname_s}"; else echo "{uname_m}"; fi\n',
                    encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    script = f'source "{INSTALL_SH}"; detect_platform'
    proc = _run(["bash", "-c", script],
                env={**os.environ, "PATH": f"{bindir}:/usr/bin:/bin"})
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@needs_posix
def test_detect_matrix(tmp_path: Path):
    assert _source_detect("Linux", "x86_64", tmp_path) == "linux-x86_64"
    assert _source_detect("Linux", "aarch64", tmp_path) == "linux-aarch64"
    assert _source_detect("Darwin", "arm64", tmp_path) == "macos-arm64"
    assert _source_detect("Darwin", "x86_64", tmp_path) == "macos-x86_64"
    assert _source_detect("FreeBSD", "x86_64", tmp_path) == "unsupported"


@needs_posix
def test_unsupported_suggests_pip(tmp_path: Path):
    bindir = tmp_path / "bin2"
    bindir.mkdir(exist_ok=True)
    stub = bindir / "uname"
    stub.write_text('#!/usr/bin/env bash\necho "FreeBSD"\n', encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    proc = _run(["bash", str(INSTALL_SH)],
                env={**os.environ, "PATH": f"{bindir}:/usr/bin:/bin"})
    assert proc.returncode == 1
    assert "pip install" in proc.stdout


def _serve_dir(directory: Path):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


@needs_posix
def test_local_install_happy_path(tmp_path: Path):
    """Alur penuh lawan server lokal + binary fake (cepat, tanpa 90MB)."""
    srv = tmp_path / "srv"
    srv.mkdir()
    # Sediakan semua nama platform — runner CI apa pun (linux/mac) ketemu.
    for plat in ("linux-x86_64", "linux-aarch64", "macos-x86_64",
                 "macos-arm64", "termux-aarch64"):
        fake = srv / f"multacd-{plat}"
        fake.write_text('#!/usr/bin/env bash\necho "multacd 0.9.0-test"\n',
                        encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    server = _serve_dir(srv)
    try:
        port = server.server_address[1]
        destdir = tmp_path / "dest"
        destdir.mkdir()
        proc = _run(
            ["bash", str(INSTALL_SH)],
            env={**os.environ,
                 "MULTACD_BINARY_BASE": f"http://127.0.0.1:{port}",
                 "MULTACD_INSTALL_DIR": str(destdir)})
    finally:
        server.shutdown()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0.9.0-test" in proc.stdout
    installed = destdir / "multacd"
    assert installed.is_file() and installed.stat().st_mode & stat.S_IEXEC


def test_ps1_markers():
    """pwsh tak ada di CI Linux — guard konten penting saja."""
    src = INSTALL_PS1.read_text(encoding="utf-8")
    assert "multacd-windows-x86_64.exe" in src
    assert "LOCALAPPDATA" in src
    assert "SetEnvironmentVariable" in src and '"PATH"' in src
    assert "--version" in src
    assert "prototypeall850-creator/multacd" in src
