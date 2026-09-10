"""git_merge — merge branch + lapor conflict terstruktur. AUTO-APPROVED.

Clean merge → ok("...").
Conflict → ok({merged: False, conflicted_files, conflicts}) agar agent
(LLM) bisa analisis ours-vs-theirs, suggest resolusi, dan apply via
edit_file + git_add setelah user setuju. Bukan fail: conflict adalah
hasil normal yang butuh keputusan user, bukan error infra.

Conflict item: {file, side, ours, theirs, line} (dipotong 40 baris/sisi).

Test cepat:
    python -m tools.git.git_merge
"""

from __future__ import annotations

import re
import subprocess
from typing import Any

from tools.common import fail, ok
from tools.git._helper import run_git, schema

SCHEMA = schema(
    "git_merge",
    "Merge branch ke branch aktif. Kalau conflict, return data ours-vs-theirs "
    "untuk dianalisis (bukan error).",
    {"branch": {"type": "string", "description": "Branch yang di-merge masuk."}},
    required=["branch"],
)

CONFLICT_RE = re.compile(
    r"^<<<<<<< (?P<ours>[^\r\n]*)$\n(?P<ours_body>.*?)^=======$\n"
    r"(?P<theirs_body>.*?)^>>>>>>> (?P<theirs>[^\r\n]*)$",
    re.MULTILINE | re.DOTALL,
)
MAX_CONFLICT_LINES = 40


def _parse_conflicts(workdir: str, files: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in files:
        try:
            with open(f"{workdir}/{name}", encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        for m in CONFLICT_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            ours = m.group("ours_body").splitlines()[:MAX_CONFLICT_LINES]
            theirs = m.group("theirs_body").splitlines()[:MAX_CONFLICT_LINES]
            out.append({"file": name, "line": line,
                        "ours": "\n".join(ours), "theirs": "\n".join(theirs)})
    return out


def git_merge(workdir: str = ".", branch: str = "") -> dict[str, Any]:
    if not branch.strip():
        return fail("Nama branch wajib diisi.")
    try:
        proc = subprocess.run(
            ["git", "-C", workdir, "merge", "--no-edit", branch.strip()],
            capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        return fail("git tidak terinstall / tidak ada di PATH")
    except (subprocess.SubprocessError, OSError) as e:
        return fail(f"Gagal merge: {e}")
    if proc.returncode == 0:
        return ok((proc.stdout or "merged").strip()[:500])

    # Gagal → cek apakah conflict (vs error biasa seperti branch tak ada).
    # NOTE: run_git mengembalikan "(tidak ada output)" untuk stdout kosong —
    # itu artinya tidak ada file conflict, bukan nama file.
    status = run_git(["diff", "--name-only", "--diff-filter=U"], workdir)
    files = [f for f in (status["result"] or "").splitlines()
             if f.strip() and f.strip() != "(tidak ada output)"]
    if not status["success"] or not files:
        err = (proc.stderr or proc.stdout or "unknown error").strip()[:300]
        return fail(f"git merge gagal: {err}")
    return ok({"merged": False, "conflicted_files": files,
               "conflicts": _parse_conflicts(workdir, files),
               "hint": "Analisis ours-vs-theirs per conflict, suggest resolusi ke user, "
                       "apply via edit_file + git_add kalau disetujui."})


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp(prefix="multacd-merge-"))
    env_branch = ["git", "-C", str(tmp)]

    def g(*args: str) -> None:
        # config lokal repo (bukan -c): merge juga butuh identitas committer.
        r = subprocess.run([*env_branch, *args], capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, (args, r.stderr)

    g("init", "-b", "main")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    (tmp / "a.txt").write_text("base\n")
    g("add", ".")
    g("commit", "-m", "init")
    g("checkout", "-b", "fitur")
    (tmp / "a.txt").write_text("versi fitur\n")
    g("commit", "-am", "fitur")
    g("checkout", "main")
    (tmp / "a.txt").write_text("versi main\n")
    g("commit", "-am", "main")

    # 1. Conflict → terstruktur ours/theirs
    r = git_merge(workdir=str(tmp), branch="fitur")
    assert r["success"], r
    assert r["result"]["merged"] is False, r
    assert r["result"]["conflicted_files"] == ["a.txt"], r
    c = r["result"]["conflicts"][0]
    assert "versi main" in c["ours"] and "versi fitur" in c["theirs"], c
    assert c["line"] >= 1
    subprocess.run([*env_branch, "merge", "--abort"], capture_output=True, timeout=30)

    # 2. Clean merge (branch tanpa conflict) → sukses
    g("checkout", "-b", "bersih")
    (tmp / "b.txt").write_text("baru\n")
    g("add", ".")
    g("commit", "-m", "b")
    g("checkout", "main")
    (tmp / "a.txt").write_text("base\n")
    g("commit", "-am", "reset")
    r = git_merge(workdir=str(tmp), branch="bersih")
    assert r["success"] and isinstance(r["result"], str), r

    # 3. Branch tak ada → fail sopan (bukan conflict)
    r = git_merge(workdir=str(tmp), branch="tak_ada")
    assert not r["success"] and "gagal" in r["error"], r

    # 4. Bukan repo / nama kosong → fail sopan
    assert not git_merge(workdir=str(tmp / "nope"), branch="x")["success"]
    assert not git_merge(workdir=str(tmp), branch="  ")["success"]

    print("✅ git_merge self-test OK (4 skenario)")
