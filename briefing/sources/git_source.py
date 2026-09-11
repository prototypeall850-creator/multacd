"""Git source — ringkasan status project (PLAN Phase 4 Step 7).

Default [cwd] + path eksplisit yang mengandung .git. Via git CLI langsung
(sync, tanpa dependensi tools.git).

Test cepat:
    python -m briefing.sources.git_source
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def get_projects(extra: list[str | Path] | None = None) -> list[Path]:
    """Project = cwd + path eksplisit bervolume .git (unik, yang ada saja)."""
    seen: list[Path] = []
    for raw in [Path.cwd(), *(Path(p) for p in (extra or []))]:
        try:
            p = raw.resolve()
        except OSError:
            continue
        if (p / ".git").is_dir() and p not in seen:
            seen.append(p)
    return seen


def _git(args: list[str], cwd: Path, timeout: int = 10) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def git_summary(path: str | Path) -> str:
    """Satu baris ringkas: 'nama (branch): N berubah, commit terakhir ...'."""
    p = Path(path)
    branch = _git(["branch", "--show-current"], p) or "?"
    porcelain = _git(["status", "--porcelain"], p)
    changed = len(porcelain.splitlines()) if porcelain else 0
    last = _git(["log", "-1", "--format=%h %s (%ar)"], p) or "belum ada commit"
    return (f"{p.name} ({branch}): {changed} file berubah, "
            f"terakhir {last}")


def get_git_status(extra: list[str | Path] | None = None) -> list[str]:
    """Ringkasan semua project yang ketemu."""
    return [git_summary(p) for p in get_projects(extra)]


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        repo = Path(d) / "demo"
        repo.mkdir()
        assert repo.resolve() not in get_projects(extra=[repo])  # bukan git
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.id"],
                       cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo,
                       check=True)
        (repo / "a.txt").write_text("hi", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "awal"], cwd=repo, check=True)
        (repo / "b.txt").write_text("baru", encoding="utf-8")
        assert repo.resolve() in get_projects(extra=[repo])
        s = git_summary(repo)
        assert "demo" in s and "1 file berubah" in s and "awal" in s, s

    print("✅ git_source self-test OK (detect + summary)")
