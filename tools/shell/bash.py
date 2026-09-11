"""bash — jalankan perintah shell. ASK-REQUIRED. ⚠️ Bisa apa saja.

Auto-detect: powershell di Windows, bash di Linux/macOS/Termux.
"""

from __future__ import annotations

import platform
from collections.abc import Callable
from typing import Any

from tools.common import fail, ok
from tools.streaming import run_streaming

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


def bash(command: str, workdir: str = ".", timeout: int = DEFAULT_TIMEOUT,
         on_output: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Jalankan shell. `on_output` opsional (live stream, bukan schema LLM)."""
    shell = detect_shell()
    res = run_streaming([*shell, command], cwd=workdir, timeout=timeout,
                        on_output=on_output)
    if res["timed_out"]:
        return fail(f"Timeout {timeout} dtk: {command}")
    if res["exit_code"] == 127 and not res["stdout"] and not res["stderr"]:
        return fail(f"Shell tidak ditemukan: {shell[0]}")
    output = (res["stdout"] or "") + (res["stderr"] or "")
    output = output.strip() or "(tidak ada output)"
    suffix = f"\n[exit code: {res['exit_code']}]" if res["exit_code"] != 0 else ""
    return ok(output + suffix)
