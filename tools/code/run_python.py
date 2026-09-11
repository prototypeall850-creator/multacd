"""run_python — jalankan file/snippet Python. ASK-REQUIRED (jalankan kode!).

Deteksi interpreter: .venv/bin/python di workdir → python3 → python di PATH.
Snippet ditulis ke temp file dulu, dihapus setelah jalan.
Timeout → process di-kill, partial output tetap dikembalikan.

NOTE: output di-stream live per baris via `on_output` (TUI tampil real-time)
kalau caller isi callback; hasil akhir tetap terkumpul utuh buat agent.

Test cepat:
    python -m tools.code.run_python
"""

from __future__ import annotations

import contextlib
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tools.common import fail
from tools.streaming import run_streaming

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "run_python",
        "description": "Jalankan file .py atau snippet Python, tangkap output. "
                       "Timeout otomatis kill process yang kelamaan.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string",
                              "description": "Path file .py (isi salah satu: ini atau code)."},
                "code": {"type": "string",
                         "description": "Snippet Python langsung (isi salah satu: ini atau file_path)."},
                "args": {"type": "string",
                         "description": "Argumen command line, mis. \"--verbose out.txt\".",
                         "default": ""},
                "workdir": {"type": "string", "description": "Folder kerja.", "default": "."},
                "timeout": {"type": "integer", "description": "Batas detik.", "default": 30},
            },
            "required": [],
        },
    },
}

DEFAULT_TIMEOUT = 30


def detect_python(workdir: str = ".") -> str | None:
    """Interpreter Python: .venv di workdir dulu, lalu PATH. None kalau tak ada."""
    venv_py = Path(workdir).expanduser() / ".venv" / "bin" / "python"
    if venv_py.is_file():
        return str(venv_py)
    for candidate in ("python3", "python"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def run_python(file_path: str | None = None, code: str | None = None,
               args: str = "", workdir: str = ".",
               timeout: int = DEFAULT_TIMEOUT,
               on_output: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Jalankan Python. `on_output` opsional (live stream per baris, bukan
    bagian schema LLM — diinjeksikan dispatcher kalau didukung)."""
    if (file_path is None) == (code is None):
        return fail("Isi salah satu: `file_path` atau `code` (tidak boleh kosong/dua-duanya).")
    if timeout <= 0:
        return fail("`timeout` harus > 0 detik.")

    python = detect_python(workdir)
    if python is None:
        return fail("Python tidak ditemukan (cek PATH / .venv).")

    tmp_path: Path | None = None
    try:
        if code is not None:
            with tempfile.NamedTemporaryFile("w", suffix=".py",
                                             delete=False, encoding="utf-8") as f:
                f.write(code)
            tmp_path = Path(f.name)
            target = str(tmp_path)
        else:
            assert file_path is not None
            target = str(Path(file_path).expanduser())
            if not Path(target).is_file():
                return fail(f"File tidak ditemukan: {file_path}")

        cmd = [python, target, *(args.split() if args.strip() else [])]
        res = run_streaming(cmd, cwd=workdir, timeout=timeout,
                            on_output=on_output)
        duration = res["duration"]
        if res["timed_out"]:
            return {
                "success": False,
                "result": {
                    "stdout": res["stdout"],
                    "stderr": res["stderr"],
                    "exit_code": None,
                    "duration": duration,
                },
                "error": f"Program dihentikan karena melebihi batas waktu {timeout} detik.",
            }
        # NOTE: success=True artinya tool jalan sampai selesai (kayak bash) —
        # hasil program lihat di exit_code. Agent yang analisis stdout/stderr.
        return {
            "success": True,
            "result": {
                "stdout": res["stdout"],
                "stderr": res["stderr"],
                "exit_code": res["exit_code"],
                "duration": duration,
            },
            "error": None,
        }
    except OSError as e:
        return fail(f"Gagal jalan: {e}")
    finally:
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                tmp_path.unlink()


if __name__ == "__main__":
    # 1. Snippet sukses
    r = run_python(code="print(2 + 2)")
    assert r["success"] and r["result"]["stdout"].strip() == "4", r
    assert r["result"]["exit_code"] == 0 and r["error"] is None

    # 2. Error → exit_code non-zero + traceback di stderr, tool tetap sukses
    #    (agent yang baca & analisis, kayak tool bash)
    r = run_python(code="1/0")
    assert r["success"] and r["result"]["exit_code"] != 0, r
    assert "ZeroDivisionError" in r["result"]["stderr"], r["result"]["stderr"][-200:]

    # 3. Timeout → kill + pesan jelas
    r = run_python(code="import time; time.sleep(60)", timeout=2)
    assert not r["success"] and "melebihi batas waktu 2 detik" in r["error"], r

    # 4. Validasi: kosong/dua-duanya/timeout ngawur
    assert not run_python()["success"]
    assert not run_python(file_path="a.py", code="x=1")["success"]
    assert not run_python(code="x=1", timeout=0)["success"]
    assert "tidak ditemukan" in run_python(file_path="tak_ada.py")["error"]

    # 5. File beneran + args
    import tempfile as _t
    with _t.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write("import sys; print('args:', ' '.join(sys.argv[1:]))\n")
        name = f.name
    r = run_python(file_path=name, args="--verbose out.txt")
    assert r["success"] and "args: --verbose out.txt" in r["result"]["stdout"], r
    Path(name).unlink()

    # 6. Deteksi venv repo sendiri
    import os as _os
    if _os.path.isdir(".venv"):
        assert run_python(code="import sys; print(sys.prefix)")["success"]
        assert ".venv" in detect_python("."), detect_python(".")

    print("✅ run_python self-test OK (6 skenario)")
