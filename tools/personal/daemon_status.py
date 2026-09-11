"""daemon_status — status daemon, bot, scheduler. AUTO-APPROVED.

PID-file management pindah ke daemon/process.py (Step 8) — tool ini baca
via helper di sana biar satu sumber. Untuk sekarang baca langsung.

Test cepat:
    python -m tools.personal.daemon_status
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tools.common import ok


def pid_file() -> Path:
    """~/.multacd/daemon.pid (hormati MULTACD_HOME)."""
    return Path(os.environ.get("MULTACD_HOME", str(Path.home()))) / ".multacd" / "daemon.pid"


def daemon_info() -> dict[str, Any]:
    """{running, pid, uptime} — False kalau PID file tidak ada/mati."""
    p = pid_file()
    if not p.is_file():
        return {"running": False, "pid": None, "uptime": "-"}
    try:
        pid = int(p.read_text(encoding="utf-8").strip().split()[0])
    except (ValueError, OSError):
        return {"running": False, "pid": None, "uptime": "-"}
    try:
        os.kill(pid, 0)  # cek proses masih hidup (POSIX)
    except (OSError, PermissionError):
        return {"running": False, "pid": pid, "uptime": "-"}
    import datetime
    up = datetime.datetime.now() - datetime.datetime.fromtimestamp(
        p.stat().st_mtime)
    mins = int(up.total_seconds() // 60)
    pretty = f"{mins // 60}h {mins % 60}m" if mins >= 60 else f"{mins}m"
    return {"running": True, "pid": pid, "uptime": pretty}


SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "daemon_status",
        "description": "Cek status daemon, bot Telegram, dan scheduler.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def daemon_status() -> dict[str, Any]:
    from core.config import get_active_config, load_config
    from scheduler.engine import get_engine

    info = daemon_info()
    try:
        cfg = get_active_config() or load_config()
        bot = "terisi" if cfg.telegram.bot_token.strip() else "belum setup"
        jobs = len(get_engine().list_jobs())
    except SystemExit:
        bot, jobs = "belum setup", 0
    daemon = (f"running (PID {info['pid']}, uptime {info['uptime']})"
              if info["running"] else "stopped")
    return ok(f"Daemon: {daemon}\nBot: {bot}\nScheduler: {jobs} job(s).")


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as home:
        os.environ["MULTACD_HOME"] = home
        assert daemon_info() == {"running": False, "pid": None, "uptime": "-"}
        r = daemon_status()
        assert r["success"] and "Daemon: stopped" in r["result"], r
        del os.environ["MULTACD_HOME"]

    print("✅ daemon_status self-test OK (stopped + format)")
