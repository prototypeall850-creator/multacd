"""git_add — stage file ke index. AUTO-APPROVED (sesuai PLAN Section 6)."""

from __future__ import annotations

from typing import Any

from tools.git._helper import run_git, schema

SCHEMA = schema(
    "git_add",
    "Stage file ke index (git add).",
    {"paths": {"type": "array", "items": {"type": "string"},
                "description": "File/folder yang di-stage. Default: semua (-A)."}},
)


def git_add(workdir: str = ".", paths: list[str] | None = None) -> dict[str, Any]:
    res = run_git(["add", "-A", *paths] if paths else ["add", "-A"], workdir)
    if not res["success"]:
        return res
    return run_git(["status", "--short"], workdir)
