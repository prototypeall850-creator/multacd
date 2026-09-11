#!/usr/bin/env python3
"""multacd — Agentic TUI (Coding + Research + Personal).

Entry point:
    python main.py [--config PATH] [--model MODEL]        → TUI
    python main.py --daemon [--config PATH]               → daemon foreground
    python main.py daemon start|stop|status|logs          → kelola background
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contextlib

from core.config import load_config
from tui.app import APP_VERSION, MultacdApp


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="multacd",
        description="Agentic TUI — coding agent di terminal (BYOK).",
    )
    p.add_argument("--config", default=None,
                   help="Path config.yaml (default: ~/.multacd/config.yaml)")
    p.add_argument("--model", default=None,
                   help="Override model (format LiteLLM, mis. groq/llama-3.3-70b-versatile)")
    p.add_argument("--version", action="store_true", help="Tampilkan versi & keluar")
    p.add_argument("--daemon", action="store_true",
                   help="Jalan sebagai daemon foreground (bot + scheduler, tanpa TUI)")
    p.add_argument("--daemon-run", action="store_true",
                   help=argparse.SUPPRESS)  # internal: target child daemon_start
    sub = p.add_subparsers(dest="cmd", metavar="{daemon,update}")
    d = sub.add_parser("daemon", help="Kelola daemon background")
    d.add_argument("action", choices=["start", "stop", "status", "logs"],
                   help="start = jalan background · logs = lihat log")
    d.add_argument("-n", "--lines", type=int, default=50,
                   help="baris log ditampilkan (default 50)")
    d.add_argument("-f", "--follow", action="store_true",
                   help="tail -f log (Ctrl+C berhenti)")
    sub.add_parser("update", help="Update multacd ke versi terbaru (via pip)")
    return p.parse_args(argv)


def _run_daemon_cmd(args: argparse.Namespace) -> int:
    """Handler `python main.py daemon ...`. Return exit code."""
    from daemon import ipc as _ipc
    from daemon.process import daemon_start, daemon_stop, is_running, log_file, read_pid

    if args.action == "start":
        print(daemon_start(args.config))
        return 0
    if args.action == "stop":
        print(daemon_stop())
        return 0
    if args.action == "status":
        pid = read_pid()
        if not is_running(pid):
            print("Daemon: stopped")
            return 0
        live = _ipc.send("status")
        if live["ok"]:
            result = live["result"]
            print(f"Daemon: running (PID {pid})")
            print(f"Bot: {result.get('bot', '?')}")
            for job in result.get("jobs", []):
                print(f"  - {job['name']}: {job['cron']} → {job['action']} "
                      f"(next: {job['next_run']})")
        else:
            print(f"Daemon: running (PID {pid}) — IPC: {live['error']}")
        return 0
    # logs
    log = log_file()
    if not log.is_file():
        print("(belum ada log)")
        return 0
    if args.follow:
        import subprocess as _sp
        with contextlib.suppress(KeyboardInterrupt):
            _sp.run(["tail", "-f", "-n", str(args.lines), str(log)])
        return 0
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    print("\n".join(lines[-args.lines:]) or "(log kosong)")
    return 0


def _run_update() -> int:
    """`multacd update`: pip install --upgrade. Binary → instruksi installer."""
    import subprocess as _sp

    from core.updater import get_current_version

    if getattr(sys, "frozen", False):
        print("⬆️ Kamu pakai binary standalone — update via installer:")
        print("   Linux/macOS/Termux: curl -fsSL https://get.multacd.dev | bash")
        print("   Windows: irm https://get.multacd.dev/install.ps1 | iex")
        return 0
    before = get_current_version()
    print(f"⬆️ versi sekarang: {before} — mengupdate via pip...")
    try:
        proc = _sp.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "multacd"],
            capture_output=True, text=True, timeout=300,
        )
    except Exception as e:
        print(f"❌ update gagal ({type(e).__name__}: {e})")
        print("   Coba manual: pip install --upgrade multacd")
        return 1
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        print("❌ update gagal:")
        for line in tail:
            print(f"   {line}")
        return 1
    after = get_current_version()
    if after != before:
        print(f"✅ update selesai: {before} → {after}. Restart multacd.")
    else:
        print(f"✅ sudah versi terbaru ({after}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.version:
        print(f"multacd {APP_VERSION}")
        return 0
    if args.cmd == "daemon":
        return _run_daemon_cmd(args)
    if args.cmd == "update":
        return _run_update()

    try:
        cfg = load_config(args.config)
    except SystemExit:
        # Config belum ada → wizard (bukan error). Config rusak → tetap error.
        from core.config import resolve_config_path

        if resolve_config_path(args.config).is_file():
            return 1  # pesan error sudah dicetak config.py
        from tui.screens.setup_wizard import run_setup_wizard

        saved = run_setup_wizard(resolve_config_path(args.config))
        if saved is None:
            print("Setup dibatalkan — sampai jumpa lagi. 👋")
            return 1
        try:
            cfg = load_config(args.config)
        except SystemExit as e:
            return int(e.code or 1)
    except Exception as e:
        print(f"❌ Gagal load config: {e}", file=sys.stderr)
        return 1

    if args.model:
        if not args.model.strip():
            print("❌ --model tidak boleh kosong.", file=sys.stderr)
            return 1
        cfg.model = args.model.strip()

    if args.daemon or args.daemon_run:
        # Daemon: tanpa TUI, tanpa wizard (config wajib sudah ada).
        from daemon.process import run_daemon
        print("👻 daemon mode: scheduler + bot, tanpa TUI. "
              "Ctrl+C / daemon stop untuk berhenti.")
        return run_daemon(cfg)

    try:
        MultacdApp(cfg, version=APP_VERSION).run()
    except KeyboardInterrupt:
        print("\n👋 Bye!")
    except Exception as e:
        # Jangan muntahkan traceback mentah ke user.
        print(f"❌ multacd berhenti karena error tak terduga ({type(e).__name__}): {e}",
              file=sys.stderr)
        print("   Coba lagi; kalau berulang, cek config & koneksi internet.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
