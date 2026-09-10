"""Helper git: satu pintu jalankan `git ...` via subprocess."""

from __future__ import annotations

import subprocess
from typing import Any

from tools.common import fail, ok


def run_git(args: list[str], workdir: str = ".") -> dict[str, Any]:
    """Jalankan git, return ok(stdout) atau fail(pesan + stderr)."""
    try:
        proc = subprocess.run(
            ["git", *args], cwd=workdir, capture_output=True, text=True, timeout=120,
        )
    except FileNotFoundError:
        return fail("git tidak terinstall / tidak ada di PATH")
    except subprocess.TimeoutExpired:
        return fail(f"git timeout: git {' '.join(args)}")
    except OSError as e:
        return fail(f"Gagal jalankan git: {e}")
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "unknown error").strip()
        return fail(f"git {' '.join(args)} gagal: {err}")
    return ok(proc.stdout.strip() or "(tidak ada output)")


def schema(name: str, description: str, extra_props: dict[str, Any] | None = None,
           required: list[str] | None = None) -> dict[str, Any]:
    """Bikin JSON Schema tool git yang seragam (selalu ada workdir opsional)."""
    props: dict[str, Any] = {
        "workdir": {"type": "string", "description": "Folder repo.", "default": "."},
    }
    if extra_props:
        props.update(extra_props)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": props, "required": required or []},
        },
    }
