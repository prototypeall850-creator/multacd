"""Clipboard helper — salin teks ke clipboard sistem (buat /copy).

Rantai provider (yang pertama berhasil menang):
  Termux (termux-clipboard-set) → wl-copy → xclip → xsel →
  pbcopy (macOS) → clip/powershell (Windows).

Tak ada yang bisa (server headless / Termux:API belum install) →
fallback jujur: tulis ke ~/.multacd/clipboard.txt + kasih tau path-nya.
Tak pernah raise — return pesan buat ditampilkan ke user.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _home() -> Path:
    return Path(os.environ.get("MULTACD_HOME", str(Path.home())))


def _run(cmd: list[str], text: str) -> bool:
    try:
        proc = subprocess.run(cmd, input=text, capture_output=True,
                              text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def copy_text(text: str) -> str:
    """Salin `text`. Return pesan hasil (Indonesia, siap tampil di chat)."""
    if not text.strip():
        return "(tidak ada teks buat disalin)"
    data = text if len(text) <= 200_000 else text[:200_000] + "\n…(dipotong)"
    providers: list[tuple[str, list[str]]] = []
    if "TERMUX_VERSION" in os.environ:
        providers.append(("termux", ["termux-clipboard-set"]))
    providers += [
        ("wl-copy", ["wl-copy"]),
        ("xclip", ["xclip", "-selection", "clipboard"]),
        ("xsel", ["xsel", "--clipboard", "--input"]),
        ("pbcopy", ["pbcopy"]),
    ]
    if os.name == "nt":
        providers.append(("Windows", ["clip"]))
    for label, cmd in providers:
        if shutil.which(cmd[0]) and _run(cmd, data):
            return f"tersalin ke clipboard ({label})."
    # Fallback: file (buka + salin manual dari sana).
    try:
        p = _home() / ".multacd" / "clipboard.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data, encoding="utf-8")
        return (f"clipboard sistem tak terjangkau — teks disimpan ke {p} "
                "(buka file itu lalu salin manual).")
    except OSError as e:
        return f"gagal salin ({e})."


if __name__ == "__main__":
    import tempfile

    tmp = tempfile.mkdtemp(prefix="multacd-clip-")
    os.environ["MULTACD_HOME"] = tmp
    # Isolasikan PATH (tanpa provider clipboard) → jatuh ke file fallback.
    os.environ["PATH"] = tmp
    msg = copy_text("halo clipboard")
    assert "clipboard.txt" in msg, msg
    assert Path(tmp, ".multacd", "clipboard.txt").read_text() == "halo clipboard"
    assert "tidak ada teks" in copy_text("   ")
    print("✅ clipboard self-test OK (fallback file)")
