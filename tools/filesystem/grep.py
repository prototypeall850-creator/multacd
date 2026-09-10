"""grep — cari string/pattern dalam file. AUTO-APPROVED."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

from tools.common import fail, ok

MAX_RESULTS = 100  # lindungi context LLM

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "grep",
        "description": "Cari regex dalam file. Return daftar 'file:baris: isi'.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex yang dicari."},
                "path": {"type": "string", "description": "File atau folder.", "default": "."},
                "include": {"type": "string", "description": "Filter nama file, mis. *.py", "default": "*"},
            },
            "required": ["pattern"],
        },
    },
}

SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".hg", ".svn"}


def _iter_files(target: Path, include: str):
    if target.is_file():
        yield target
        return
    for p in target.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if fnmatch.fnmatch(p.name, include):
            yield p


def grep(pattern: str, path: str = ".", include: str = "*") -> dict[str, Any]:
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return fail(f"Regex tidak valid `{pattern}`: {e}")
    target = Path(path).expanduser()
    if not target.exists():
        return fail(f"Path tidak ditemukan: {path}")
    hits: list[str] = []
    truncated = False
    for f in _iter_files(target, include):
        try:
            raw = f.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:4096]:
            continue  # binary — skip
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{f}:{i}: {line.strip()[:300]}")
                if len(hits) >= MAX_RESULTS:
                    truncated = True
                    break
        if truncated:
            break
    if truncated:
        hits.append(f"[...dipotong: > {MAX_RESULTS} hasil, persempit pattern/filter...]")
    return ok(hits)
