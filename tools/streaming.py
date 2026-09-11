"""Streaming subprocess — output live per baris + buffer penuh.

Dipakai tool long-running (run_python, run_tests, bash) biar TUI tidak
diam: tiap baris stdout/stderr diteruskan ke `on_output` saat itu juga,
sementara hasil akhir tetap terkumpul utuh buat agent.

Threading: reader jalan di thread daemon; `on_output` dipanggil dari
thread itu — caller yang butuh event loop (TUI) wajib marshal sendiri
(mis. `app.call_from_thread`). Callback yang raise → diabaikan
(streaming jalan terus, tak pernah crash gara-gara consumer).
"""

from __future__ import annotations

import contextlib
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any

#Saveram: output program liar (infinite print) tak boleh makan RAM.
MAX_BUFFER_CHARS = 500_000


def run_streaming(cmd: Sequence[str], *, cwd: str = ".",
                  timeout: int = 60,
                  on_output: Callable[[str], None] | None = None,
                  ) -> dict[str, Any]:
    """Jalankan cmd; stream tiap baris ke on_output. Return dict hasil.

    Keys: stdout, stderr, exit_code (None kalau timeout), duration,
    timed_out (bool). Buffer dipotong MAX_BUFFER_CHARS + marker.
    """
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            list(cmd), cwd=cwd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
    except FileNotFoundError as e:
        return {"stdout": "", "stderr": str(e), "exit_code": 127,
                "duration": 0.0, "timed_out": False}
    except OSError as e:
        return {"stdout": "", "stderr": str(e), "exit_code": 127,
                "duration": 0.0, "timed_out": False}

    assert proc.stdout is not None and proc.stderr is not None
    out_parts: list[str] = []
    err_parts: list[str] = []
    lock = threading.Lock()

    def _pump(stream, parts: list[str]) -> None:
        try:
            for line in iter(stream.readline, ""):
                text = line.rstrip("\n")
                with lock:
                    parts.append(line)
                if on_output is not None:
                    with contextlib.suppress(Exception):
                        on_output(text)
        finally:
            with contextlib.suppress(Exception):
                stream.close()

    threads = [
        threading.Thread(target=_pump, args=(proc.stdout, out_parts),
                         daemon=True),
        threading.Thread(target=_pump, args=(proc.stderr, err_parts),
                         daemon=True),
    ]
    for t in threads:
        t.start()
    try:
        proc.wait(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()
    for t in threads:
        t.join(timeout=5)
    duration = round(time.monotonic() - started, 2)

    stdout = "".join(out_parts)
    stderr = "".join(err_parts)
    if len(stdout) > MAX_BUFFER_CHARS:
        stdout = stdout[:MAX_BUFFER_CHARS] + "\n…(output dipotong)"
    if len(stderr) > MAX_BUFFER_CHARS:
        stderr = stderr[:MAX_BUFFER_CHARS] + "\n…(output dipotong)"
    return {"stdout": stdout, "stderr": stderr,
            "exit_code": None if timed_out else proc.returncode,
            "duration": duration, "timed_out": timed_out}


if __name__ == "__main__":
    import sys

    # 1. Echo biasa + live callback per baris
    seen: list[str] = []
    r = run_streaming([sys.executable, "-c", "print('a'); print('b')"],
                      on_output=seen.append, timeout=10)
    assert r["exit_code"] == 0 and not r["timed_out"], r
    assert seen == ["a", "b"], seen
    assert r["stdout"] == "a\nb\n", repr(r["stdout"])

    # 2. Stderr ikut ke-stream, exit code non-zero
    seen.clear()
    r = run_streaming(
        [sys.executable, "-c",
         "import sys; print('out'); print('err', file=sys.stderr); "
         "sys.exit(3)"],
        on_output=seen.append, timeout=10)
    assert r["exit_code"] == 3, r
    assert sorted(seen) == ["err", "out"], seen
    assert r["stderr"] == "err\n", repr(r["stderr"])

    # 3. Timeout → kill + partial output + flag
    seen.clear()
    r = run_streaming(
        [sys.executable, "-c",
         "import time; print('dini', flush=True); time.sleep(60)"],
        on_output=seen.append, timeout=2)
    assert r["timed_out"] and r["exit_code"] is None, r
    assert seen == ["dini"] and "dini" in r["stdout"], (seen, r)

    # 4. Tanpa callback tetap jalan (kompat lama)
    r = run_streaming([sys.executable, "-c", "print(2+2)"], timeout=10)
    assert r["stdout"].strip() == "4" and r["exit_code"] == 0

    # 5. Command ngawur → exit 127, bukan raise
    r = run_streaming(["multacd-tak-ada-xyz"], timeout=10)
    assert r["exit_code"] == 127 and not r["timed_out"]

    # 6. Callback ngamuk → streaming tetap selesai
    def _boom(line: str) -> None:
        raise RuntimeError("consumer rusak")
    r = run_streaming([sys.executable, "-c", "print('x')"],
                      on_output=_boom, timeout=10)
    assert r["exit_code"] == 0 and r["stdout"] == "x\n"

    print("✅ streaming self-test OK (6 skenario)")
