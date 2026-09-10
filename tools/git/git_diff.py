"""git_diff — lihat perubahan belum di-commit. AUTO-APPROVED."""

from __future__ import annotations

from typing import Any

from tools.git._helper import run_git, schema

SCHEMA = schema(
    "git_diff",
    "Lihat diff perubahan (unstaged default; staged kalau staged=True).",
    {"staged": {"type": "boolean", "description": "Diff area staged (--cached).", "default": False}},
)


def git_diff(workdir: str = ".", staged: bool = False) -> dict[str, Any]:
    args = ["diff", "--cached"] if staged else ["diff"]
    return run_git(args, workdir)
