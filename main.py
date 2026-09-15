#!/usr/bin/env python3
"""multacd — Agentic TUI (Coding + Research).

Entry point:
    python main.py [--config PATH] [--model MODEL]        → TUI
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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
    sub = p.add_subparsers(dest="cmd", metavar="{update}")
    sub.add_parser("update", help="Update multacd ke versi terbaru (via pip)")
    return p.parse_args(argv)


def _run_update() -> int:
    """`multacd update`: pip install --upgrade. Binary → instruksi installer."""
    import subprocess as _sp

    from core.updater import get_current_version

    if getattr(sys, "frozen", False):
        print("Kamu pakai binary standalone — update via installer:")
        print("   Linux/macOS/Termux: curl -fsSL https://get.multacd.dev | bash")
        print("   Windows: irm https://get.multacd.dev/install.ps1 | iex")
        return 0
    before = get_current_version()
    print(f"Update: versi sekarang {before} — mengupdate via pip...")
    try:
        proc = _sp.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "multacd"],
            capture_output=True, text=True, timeout=300,
        )
    except Exception as e:
        print(f"Update gagal ({type(e).__name__}: {e})")
        print("   Coba manual: pip install --upgrade multacd")
        return 1
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        print("Update gagal:")
        for line in tail:
            print(f"   {line}")
        return 1
    after = get_current_version()
    if after != before:
        print(f"Update selesai: {before} → {after}. Restart multacd.")
    else:
        print(f"Sudah versi terbaru ({after}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.version:
        print(f"multacd {APP_VERSION}")
        return 0
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
            print("Setup dibatalkan.")
            return 1
        try:
            cfg = load_config(args.config)
        except SystemExit as e:
            return int(e.code or 1)
    except Exception as e:
        print(f"Gagal load config: {e}", file=sys.stderr)
        return 1

    if args.model:
        if not args.model.strip():
            print("--model tidak boleh kosong.", file=sys.stderr)
            return 1
        cfg.model = args.model.strip()

    try:
        MultacdApp(cfg, version=APP_VERSION).run()
    except KeyboardInterrupt:
        print("\nBye!")
    except Exception as e:
        # Jangan muntahkan traceback mentah ke user.
        print(f"multacd berhenti karena error tak terduga ({type(e).__name__}): {e}",
              file=sys.stderr)
        print("   Coba lagi; kalau berulang, cek config & koneksi internet.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def app() -> None:
    """Entry point resmi console_scripts (lihat pyproject [project.scripts]).

    `pip install -e .` → perintah `multacd` di terminal memanggil ini.
    """
    raise SystemExit(main())
