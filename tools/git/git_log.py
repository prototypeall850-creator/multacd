"""git_log — lihat history commit. AUTO-APPROVED."""

from __future__ import annotations

from typing import Any

from tools.git._helper import run_git, schema

SCHEMA = schema(
    "git_log",
    "Lihat history commit (oneline, terbaru dulu).",
    {"limit": {"type": "integer", "description": "Jumlah commit.", "default": 10}},
)


def git_log(workdir: str = ".", limit: int = 10) -> dict[str, Any]:
    return run_git(["log", f"-{max(1, limit)}", "--oneline", "--decorate"], workdir)
