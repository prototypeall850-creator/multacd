"""git_push — push ke remote. AUTO-APPROVED, KECUALI branch dilindungi.

Branch di PROTECTED_BRANCHES butuh opt-in eksplisit (`allow_protected=true`).
Tanpa itu → fail dengan pesan yang nyuruh agent tawarkan opsi ke user
(push tetap / buat branch baru / batal). Cara agent minta izin: tool `ask`
atau chat; dialog konfirmasi khusus (dengan tombol buat-branch) = polish
TUI Step 8.

Test cepat:
    python -m tools.git.git_push
"""

from __future__ import annotations

import subprocess
from typing import Any

from tools.common import fail
from tools.git._helper import run_git, schema

PROTECTED_BRANCHES = frozenset({
    "main", "master", "production", "prod", "release", "stable",
})

SCHEMA = schema(
    "git_push",
    "Push branch aktif ke remote. Branch utama (main/master/...) butuh "
    "allow_protected=true — kalau ditolak, tawarkan buat branch baru.",
    {
        "remote": {"type": "string", "default": "origin"},
        "branch": {"type": "string", "description": "Default: branch aktif."},
        "allow_protected": {"type": "boolean",
                            "description": "Wajib true untuk push ke branch utama.",
                            "default": False},
    },
)


def _current_branch(workdir: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", workdir, "branch", "--show-current"],
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def git_push(workdir: str = ".", remote: str = "origin", branch: str = "",
             allow_protected: bool = False) -> dict[str, Any]:
    target = branch.strip() or (_current_branch(workdir) or "")
    if target in PROTECTED_BRANCHES and not allow_protected:
        return fail(
            f"⛔ Branch `{target}` dilindungi. Jangan push langsung — "
            "tanyakan user dulu: (1) tetap push ke branch ini, "
            "(2) buat branch baru lalu push, atau (3) batal. "
            "Kalau user pilih (1), ulangi tool ini dengan allow_protected=true.")
    if branch:
        return run_git(["push", remote, branch], workdir)
    return run_git(["push", remote], workdir)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp(prefix="multacd-push-"))
    subprocess.run(["git", "-C", str(tmp), "init", "-b", "main"],
                   capture_output=True, timeout=30, check=True)

    # 1. Push ke main tanpa opt-in → diblok SEBELUM sentuh network
    r = git_push(workdir=str(tmp))
    assert not r["success"] and "dilindungi" in r["error"], r
    assert "allow_protected=true" in r["error"], r

    # 2. allow_protected=true → lolos gate (gagal di network, bukan gate)
    r = git_push(workdir=str(tmp), allow_protected=True)
    assert not r["success"] and "dilindungi" not in r["error"], r

    # 3. Branch biasa → tidak diblok gate
    subprocess.run(["git", "-C", str(tmp), "checkout", "-b", "fitur"],
                   capture_output=True, timeout=30, check=True)
    r = git_push(workdir=str(tmp))
    assert not r["success"] and "dilindungi" not in r["error"], r

    # 4. Param branch eksplisit ke protected → tetap diblok
    r = git_push(workdir=str(tmp), branch="production")
    assert not r["success"] and "dilindungi" in r["error"], r

    print("✅ git_push self-test OK (4 skenario)")
