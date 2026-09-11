"""run_tests — jalankan pytest. ASK-REQUIRED (jalankan kode).

Return (sukses = pytest jalan sampai selesai, apapun hasilnya):
    {success, passed, failed, errors, skipped, duration, details}
details = [{name, status, message}] hanya untuk yang gagal/error.

Infra gagal (pytest hilang, path ngawur, timeout) → success False.

Test cepat:
    python -m tools.code.run_tests
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tools.common import fail, ok
from tools.streaming import run_streaming

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "run_tests",
        "description": "Jalankan pytest (semua / spesifik). Return summary + detail gagal.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string",
                         "description": "Folder/file test (default: cari otomatis).",
                         "default": "."},
                "test_name": {"type": "string",
                              "description": "Filter -k, mis. test_login.",
                              "default": ""},
                "verbose": {"type": "string",
                            "description": "true = output -vv.",
                            "default": "false"},
            },
            "required": [],
        },
    },
}

DEFAULT_TIMEOUT = 120
_RESULT_RE = re.compile(r"^(?P<name>\S+) (?P<status>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)")
_FAIL_RE = re.compile(r"^(FAILED|ERROR) (?P<name>\S+)( - (?P<msg>.*))?$")
_DURATION_RE = re.compile(r"in (?P<dur>[\d.]+)s")


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def detect_pytest(workdir: str = ".") -> str | None:
    venv_pytest = Path(workdir).expanduser() / ".venv" / "bin" / "pytest"
    if venv_pytest.is_file():
        return str(venv_pytest)
    return shutil.which("pytest")


def run_tests(path: str = ".", test_name: str = "",
              verbose: object = False,
              timeout: int = DEFAULT_TIMEOUT,
              on_output: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Jalankan pytest. `on_output` opsional (live stream, bukan schema LLM)."""
    pytest = detect_pytest(".")
    if pytest is None:
        return fail("pytest belum terinstall — jalankan: pip install pytest")
    if not Path(path).expanduser().exists():
        return fail(f"Path tidak ditemukan: {path}")
    if timeout <= 0:
        return fail("`timeout` harus > 0 detik.")

    cmd = [pytest, path, "--tb=short", "-rf", "--no-header", "-p", "no:cacheprovider"]
    cmd.append("-vv" if _as_bool(verbose) else "-v")
    if test_name.strip():
        cmd += ["-k", test_name.strip()]

    try:
        res = run_streaming(cmd, timeout=timeout, on_output=on_output)
    except OSError as e:
        return fail(f"Gagal jalan pytest: {e}")
    if res["timed_out"]:
        return fail(f"Test dihentikan karena melebihi batas waktu {timeout} detik.")
    duration = res["duration"]
    out = res["stdout"] or ""
    exit_code = res["exit_code"] if res["exit_code"] is not None else 1

    if exit_code == 5 or "no tests ran" in out:
        return fail(f"Tidak ada test yang ke-collect di: {path}")

    passed = failed = errors = skipped = 0
    failed_names: dict[str, str] = {}
    for line in out.splitlines():
        m = _RESULT_RE.match(line.strip())
        if m:
            st = m.group("status")
            if st == "PASSED":
                passed += 1
            elif st == "FAILED":
                failed += 1
            elif st == "ERROR":
                errors += 1
            elif st in ("SKIPPED", "XFAIL"):
                skipped += 1
            elif st == "XPASS":
                failed += 1
        m2 = _FAIL_RE.match(line.strip())
        if m2:
            failed_names[m2.group("name")] = (m2.group("msg") or "").strip()

    details = [{"name": n, "status": "failed", "message": msg}
               for n, msg in failed_names.items()]
    total = passed + failed + errors + skipped
    summary = (f"{passed}/{total} passed"
               + (f", {failed} failed" if failed else "")
               + (f", {errors} error" if errors else "")
               + (f", {skipped} skipped" if skipped else ""))
    result = {"success": failed == 0 and errors == 0,
              "passed": passed, "failed": failed, "errors": errors,
              "skipped": skipped, "duration": duration,
              "details": details, "summary": summary}
    return ok(result)


if __name__ == "__main__":
    import tempfile as _t

    tmp = Path(_t.mkdtemp(prefix="multacd-pytest-"))
    (tmp / "test_demo.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n"
        "\n\ndef test_gagal():\n    assert 1 + 1 == 3\n")

    # 1. Campuran pass + fail → summary + detail nama test
    r = run_tests(path=str(tmp))
    assert r["success"], r
    res = r["result"]
    assert res["passed"] == 1 and res["failed"] == 1, res
    assert len(res["details"]) == 1 and "test_gagal" in res["details"][0]["name"], res
    assert res["details"][0]["status"] == "failed"

    # 2. Filter -k → cuma yang cocok yang jalan
    r = run_tests(path=str(tmp), test_name="test_ok")
    assert r["success"] and r["result"]["passed"] == 1 and r["result"]["failed"] == 0, r

    # 3. Folder tanpa test → fail sopan (bukan crash)
    empty = Path(_t.mkdtemp(prefix="multacd-empty-"))
    assert not run_tests(path=str(empty))["success"]

    # 4. Path ngawur → fail sopan
    assert not run_tests(path=str(tmp / "nope"))["success"]

    print("✅ run_tests self-test OK (4 skenario)")
