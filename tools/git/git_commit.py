"""git_commit — commit perubahan. AUTO-APPROVED (sesuai PLAN Section 6)."""

from __future__ import annotations

from typing import Any

from tools.git._helper import run_git, schema

SCHEMA = schema(
    "git_commit",
    "Commit perubahan yang sudah di-stage.",
    {"message": {"type": "string", "description": "Pesan commit."}},
    required=["message"],
)


def git_commit(workdir: str = ".", message: str = "") -> dict[str, Any]:
    if not message.strip():
        from tools.common import fail
        return fail("Pesan commit wajib diisi.")
    return run_git(["commit", "-m", message], workdir)
