"""git_branch — lihat daftar branch. AUTO-APPROVED."""

from __future__ import annotations

from typing import Any

from tools.git._helper import run_git, schema

SCHEMA = schema("git_branch", "Lihat daftar branch lokal (tanda * = aktif).")


def git_branch(workdir: str = ".") -> dict[str, Any]:
    return run_git(["branch", "--list"], workdir)
