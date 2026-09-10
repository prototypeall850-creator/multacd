"""git_push — push ke remote. AUTO-APPROVED (sesuai PLAN Section 6)."""

from __future__ import annotations

from typing import Any

from tools.git._helper import run_git, schema

SCHEMA = schema(
    "git_push",
    "Push branch aktif ke remote.",
    {
        "remote": {"type": "string", "default": "origin"},
        "branch": {"type": "string", "description": "Default: branch aktif."},
    },
)


def git_push(workdir: str = ".", remote: str = "origin", branch: str = "") -> dict[str, Any]:
    if branch:
        return run_git(["push", remote, branch], workdir)
    return run_git(["push", remote], workdir)
