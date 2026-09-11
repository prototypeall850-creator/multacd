"""Daemon process — start/stop/status + serve loop (PLAN Phase 4 Step 8).

Start = spawn detached child (`main.py --daemon-run`) via start_new_session.
Child = scheduler + bot Telegram + IPC socket, tanpa TUI.
Tanpa bot_token → mode scheduler-only (warning, bukan error).

Test cepat:
    python -m daemon.process
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any


def pid_file() -> Path:
    """~/.multacd/daemon.pid (hormati MULTACD_HOME)."""
    return Path(os.environ.get("MULTACD_HOME", str(Path.home()))) / ".multacd" / "daemon.pid"


def log_file() -> Path:
    """~/.multacd/daemon.log (hormati MULTACD_HOME)."""
    return Path(os.environ.get("MULTACD_HOME", str(Path.home()))) / ".multacd" / "daemon.log"


def read_pid() -> int | None:
    """PID dari file, atau None kalau tidak ada/rusak."""
    try:
        return int(pid_file().read_text(encoding="utf-8").strip().split()[0])
    except (ValueError, OSError):
        return None


def is_running(pid: int | None = None) -> bool:
    """Cek proses masih hidup (POSIX kill 0)."""
    pid = read_pid() if pid is None else pid
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, PermissionError):
        return False
    return True


def daemon_start(config_path: str | None = None) -> str:
    """Spawn detached child. Idempotent — sudah jalan → lapor PID."""
    pid = read_pid()
    if is_running(pid):
        return f"Daemon sudah berjalan (PID: {pid})."
    if pid is not None:
        with suppress(OSError):
            pid_file().unlink()  # stale, bersihkan
    main_py = Path(__file__).resolve().parent.parent / "main.py"
    cmd = [sys.executable, str(main_py), "--daemon-run"]
    if config_path:
        cmd += ["--config", config_path]
    try:
        with open(log_file(), "a", encoding="utf-8") as log:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
    except OSError as e:
        return f"Gagal start daemon: {e}"
    pid_file().parent.mkdir(parents=True, exist_ok=True)
    pid_file().write_text(str(proc.pid), encoding="utf-8")
    return f"Daemon start (PID: {proc.pid}). Log: {log_file()}"


def daemon_stop() -> str:
    """Hentikan daemon (TERM → KILL). Idempotent."""
    pid = read_pid()
    if not is_running(pid):
        with suppress(OSError):
            pid_file().unlink(missing_ok=True)
        return "Daemon tidak jalan."
    assert pid is not None
    with suppress(ProcessLookupError, PermissionError):
        os.kill(pid, signal.SIGTERM)
    for _ in range(25):  # tunggu mati ≤ 5 dtk
        import time
        time.sleep(0.2)
        if not is_running(pid):
            break
    if is_running(pid):
        with suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)
    with suppress(OSError):
        pid_file().unlink(missing_ok=True)
    return f"Daemon berhenti (PID {pid})."


async def _serve(config: Any) -> None:
    """Loop utama child: scheduler + bot + IPC sampai SIGTERM/SIGINT."""
    from core.config import set_active_config
    from daemon import ipc as _ipc
    from scheduler.engine import get_engine

    set_active_config(config)
    from core.plugin_loader import load_all as _load_plugins
    _plug = _load_plugins()
    if _plug.plugins:
        print(f"plugin aktif: {', '.join(p.name for p in _plug.plugins)}",
              flush=True)
    for w in _plug.warnings:
        print(f"plugin warning: {w}", flush=True)
    engine = get_engine()
    loaded = engine.load_from_config(config)
    print(f"scheduler: {len(loaded['loaded'])} dari config, "
          f"{len(engine.list_jobs())} total di tabel.", flush=True)

    bot = None
    if (config.telegram.bot_token or "").strip():
        from tg.bot import MultacdBot
        try:
            bot = MultacdBot(config)
        except ValueError as e:
            # Token ngawur (bukan kosong) → jangan crash daemon,
            # scheduler tetap jalan, admin baca log.
            print(f"bot tidak jalan ({e}) — mode scheduler-only.",
                  flush=True)
    else:
        print("tanpa bot_token — mode scheduler-only.", flush=True)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(RuntimeError, ValueError):
            loop.add_signal_handler(sig, stop.set)

    def _ipc_status() -> dict[str, Any]:
        return {"pid": os.getpid(), "jobs": engine.list_jobs(),
                "bot": "online" if bot else "off (tanpa token)"}

    ipc_task = asyncio.create_task(_ipc.serve_forever({
        "ping": lambda: "pong",
        "status": _ipc_status,
        "jobs": lambda: engine.list_jobs(),
    }))
    engine.start()
    if bot is not None:
        await bot.app.initialize()
        await bot.app.start()
        await bot.app.updater.start_polling()
        print("bot polling jalan.", flush=True)
    await stop.wait()
    print("shutdown...", flush=True)
    ipc_task.cancel()
    if bot is not None:
        with suppress(Exception):
            await bot.app.updater.stop()
            await bot.app.stop()
            await bot.app.shutdown()
    engine.shutdown(wait=False)


def run_daemon(config: Any) -> int:
    """Entry child --daemon-run (blocking). Return exit code."""
    with suppress(KeyboardInterrupt):
        asyncio.run(_serve(config))
    return 0


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as home:
        os.environ["MULTACD_HOME"] = home
        assert not is_running() and read_pid() is None
        assert daemon_stop() == "Daemon tidak jalan."

        # Fake PID hidup (proses sendiri) → guard sudah-jalan.
        pid_file().parent.mkdir(parents=True, exist_ok=True)
        pid_file().write_text(str(os.getpid()), encoding="utf-8")
        assert is_running()
        assert f"(PID: {os.getpid()})" in daemon_start()
        assert pid_file().read_text().strip() == str(os.getpid())  # tak timpa

        # Stale PID → dibersihkan lalu start coba spawn (child asli!).
        # Pakai monkeypatch Popen biar tanpa proses beneran.
        pid_file().write_text("999999999", encoding="utf-8")
        assert not is_running(999999999)
        import daemon.process as _dp
        _orig = subprocess.Popen

        class _FakeProc:
            pid = 4242

        _dp.subprocess.Popen = lambda *a, **k: _FakeProc()  # type: ignore
        try:
            msg = daemon_start()
        finally:
            _dp.subprocess.Popen = _orig
        assert "PID: 4242" in msg, msg
        assert read_pid() == 4242
        del os.environ["MULTACD_HOME"]

    print("✅ process self-test OK (guard + stale + spawn)")
