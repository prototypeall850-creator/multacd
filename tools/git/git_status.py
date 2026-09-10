"""git_status — lihat status repo. AUTO-APPROVED."""

from __future__ import annotations

from typing import Any

from tools.git._helper import run_git, schema

SCHEMA = schema("git_status", "Lihat status repo (branch, staged/unstaged/untracked).")


def git_status(workdir: str = ".") -> dict[str, Any]:
    return run_git(["status", "--short", "--branch"], workdir)
