"""git_checkout — ganti atau buat branch. AUTO-APPROVED (sesuai PLAN Section 6)."""

from __future__ import annotations

from typing import Any

from tools.git._helper import run_git, schema

SCHEMA = schema(
    "git_checkout",
    "Pindah branch (buat baru kalau create=True).",
    {
        "branch": {"type": "string", "description": "Nama branch."},
        "create": {"type": "boolean", "description": "Buat branch baru (-b).", "default": False},
    },
    required=["branch"],
)


def git_checkout(workdir: str = ".", branch: str = "", create: bool = False) -> dict[str, Any]:
    if not branch.strip():
        from tools.common import fail
        return fail("Nama branch wajib diisi.")
    args = ["checkout", "-b", branch] if create else ["checkout", branch]
    return run_git(args, workdir)
