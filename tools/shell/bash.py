"""bash — jalankan perintah shell. ASK-REQUIRED. ⚠️ Bisa apa saja.

Auto-detect: powershell di Windows, bash di Linux/macOS/Termux.
"""

from __future__ import annotations

import platform
import subprocess
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Jalankan perintah shell. Return stdout (stderr digabung). Ada timeout.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Perintah yang dijalankan."},
                "workdir": {"type": "string", "description": "Folder kerja.", "default": "."},
                "timeout": {"type": "integer", "description": "Batas detik.", "default": 60},
            },
            "required": ["command"],
        },
    },
}

DEFAULT_TIMEOUT = 60


def detect_shell() -> list[str]:
    """Perintah shell per OS: powershell (Windows) vs bash (lainnya)."""
    if platform.system() == "Windows":
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command"]
    return ["bash", "-c"]


def bash(command: str, workdir: str = ".", timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    shell = detect_shell()
    try:
        proc = subprocess.run(
            [*shell, command],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return fail(f"Shell tidak ditemukan: {shell[0]}")
    except subprocess.TimeoutExpired:
        return fail(f"Timeout {timeout} dtk: {command}")
    except OSError as e:
        return fail(f"Gagal jalan ({e}): {command}")
    output = (proc.stdout or "") + (proc.stderr or "")
    output = output.strip() or "(tidak ada output)"
    suffix = f"\n[exit code: {proc.returncode}]" if proc.returncode != 0 else ""
    return ok(output + suffix)
