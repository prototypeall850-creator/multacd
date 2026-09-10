"""lint_python — lint dengan ruff. AUTO, kecuali fix=True → ASK.

fix=False: baca saja → AUTO-APPROVED.
fix=True : ubah file → eskalasi ke ASK (lihat PermissionChecker.check
           yang menerima params; satu-satunya tool param-aware).

Return (sukses = ruff jalan, bukan nol-issue):
    {success, issues: [{file, line, column, code, message}],
     fixed_count, summary}

Test cepat:
    python -m tools.code.lint_python
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "lint_python",
        "description": "Lint file/folder Python dengan ruff. Set fix=true untuk auto-fix.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File/folder yang di-lint.",
                         "default": "."},
                "fix": {"type": "string",
                        "description": "true = auto-fix yang bisa di-fix (minta izin).",
                        "default": "false"},
            },
            "required": [],
        },
    },
}


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def detect_ruff(workdir: str = ".") -> str | None:
    venv_ruff = Path(workdir).expanduser() / ".venv" / "bin" / "ruff"
    if venv_ruff.is_file():
        return str(venv_ruff)
    return shutil.which("ruff")


def _check_once(ruff: str, path: str) -> tuple[list[dict[str, Any]], str | None]:
    """Satu putaran ruff JSON. Return (issues, error_infra)."""
    try:
        proc = subprocess.run(
            [ruff, "check", path, "--output-format", "json"],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return [], f"Gagal jalan ruff: {e}"
    # exit 0 = bersih, 1 = ada issue, 2 = error pemakaian
    if proc.returncode == 2:
        return [], (proc.stderr.strip() or "ruff error")[:300]
    try:
        raw = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return [], "Output ruff bukan JSON valid"
    issues = [{
        "file": item.get("filename", "?"),
        "line": item.get("location", {}).get("row", 0),
        "column": item.get("location", {}).get("column", 0),
        "code": item.get("code", "?"),
        "message": item.get("message", ""),
    } for item in raw]
    return issues, None


def lint_python(path: str = ".", fix: object = False) -> dict[str, Any]:
    do_fix = _as_bool(fix)
    ruff = detect_ruff(".")
    if ruff is None:
        return fail("ruff belum terinstall — jalankan: pip install ruff")
    if not Path(path).expanduser().exists():
        return fail(f"Path tidak ditemukan: {path}")

    before, err = _check_once(ruff, path)
    if err:
        return fail(err)
    fixed_count = 0
    issues = before
    if do_fix and before:
        try:
            subprocess.run([ruff, "check", path, "--fix", "--quiet"],
                           capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as e:
            return fail(f"Gagal auto-fix: {e}")
        after, err = _check_once(ruff, path)
        if err:
            return fail(err)
        fixed_count = max(0, len(before) - len(after))
        issues = after
    n_files = len({i["file"] for i in issues})
    summary = f"{len(issues)} issue di {n_files} file" if issues else "bersih, 0 issue"
    if fixed_count:
        summary += f" ({fixed_count} di-fix)"
    return ok({"success": len(issues) == 0, "issues": issues,
               "fixed_count": fixed_count, "summary": summary})


if __name__ == "__main__":
    import tempfile as _t

    tmp = Path(_t.mkdtemp(prefix="multacd-lint-"))
    bad = tmp / "bad.py"
    bad.write_text("import os\n\n\ndef f():\n    x = 1\n    return 2\n")
    good = tmp / "good.py"
    good.write_text('"""Modul bersih."""\n\n\ndef f():\n    """Return."""\n    return 2\n')

    # 1. File kotor → issue F401 (unused import) + F841 (unused var)
    r = lint_python(path=str(bad))
    assert r["success"], r
    codes = {i["code"] for i in r["result"]["issues"]}
    assert {"F401", "F841"} <= codes, codes
    assert r["result"]["fixed_count"] == 0 and "2 issue" in r["result"]["summary"], r

    # 2. File bersih → 0 issue
    r = lint_python(path=str(good))
    assert r["success"] and r["result"]["issues"] == [], r
    assert r["result"]["summary"].startswith("bersih"), r

    # 3. fix=True → F401 hilang (fixable), F841 sisa (tak auto-fixable)
    r = lint_python(path=str(bad), fix=True)
    assert r["success"] and r["result"]["fixed_count"] >= 1, r
    assert {i["code"] for i in r["result"]["issues"]} == {"F841"}, r

    # 4. Path ngawur → fail sopan
    assert not lint_python(path=str(tmp / "nope.py"))["success"]

    print("✅ lint_python self-test OK (4 skenario)")
