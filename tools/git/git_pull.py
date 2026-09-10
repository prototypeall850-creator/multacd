"""git_pull — pull dari remote. AUTO-APPROVED (sesuai PLAN Section 6)."""

from __future__ import annotations

from typing import Any

from tools.git._helper import run_git, schema

SCHEMA = schema(
    "git_pull",
    "Pull branch aktif dari remote.",
    {"remote": {"type": "string", "default": "origin"}},
)


def git_pull(workdir: str = ".", remote: str = "origin") -> dict[str, Any]:
    return run_git(["pull", remote], workdir)
