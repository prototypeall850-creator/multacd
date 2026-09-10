#!/usr/bin/env python3
"""multacd — Agentic TUI (Coding + Research + Personal).

Entry point:
    python main.py [--config PATH] [--model MODEL]
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
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.version:
        print(f"multacd {APP_VERSION}")
        return 0

    try:
        cfg = load_config(args.config)
    except SystemExit as e:
        return int(e.code or 1)  # pesan setup/error sudah dicetak config.py
    except Exception as e:
        print(f"❌ Gagal load config: {e}", file=sys.stderr)
        return 1

    if args.model:
        if not args.model.strip():
            print("❌ --model tidak boleh kosong.", file=sys.stderr)
            return 1
        cfg.model = args.model.strip()

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
