"""daemon_status — status daemon, bot, scheduler. AUTO-APPROVED.

PID-file single source di daemon/process.py (Step 8).

Test cepat:
    python -m tools.personal.daemon_status
"""

from __future__ import annotations

import datetime
import os
from typing import Any

from daemon.process import is_running, pid_file, read_pid
from tools.common import ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "daemon_status",
        "description": "Cek status daemon, bot Telegram, dan scheduler.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def _uptime_pretty() -> str:
    try:
        up = datetime.datetime.now() - datetime.datetime.fromtimestamp(
            pid_file().stat().st_mtime)
    except OSError:
        return "-"
    mins = int(up.total_seconds() // 60)
    return f"{mins // 60}h {mins % 60}m" if mins >= 60 else f"{mins}m"


def daemon_status() -> dict[str, Any]:
    from core.config import get_active_config, load_config
    from scheduler.engine import get_engine

    pid = read_pid()
    daemon = (f"running (PID {pid}, uptime {_uptime_pretty()})"
              if is_running(pid) else "stopped")
    try:
        cfg = get_active_config() or load_config()
        bot = "terisi" if cfg.telegram.bot_token.strip() else "belum setup"
        jobs = len(get_engine().list_jobs())
    except SystemExit:
        bot, jobs = "belum setup", 0
    return ok(f"Daemon: {daemon}\nBot: {bot}\nScheduler: {jobs} job(s).")


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as home:
        os.environ["MULTACD_HOME"] = home
        assert not is_running() and read_pid() is None
        r = daemon_status()
        assert r["success"] and "Daemon: stopped" in r["result"], r
        del os.environ["MULTACD_HOME"]

    print("✅ daemon_status self-test OK (stopped + format)")
