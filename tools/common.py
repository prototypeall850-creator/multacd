"""Helper bersama semua tool: format return konsisten.

Setiap tool return dict:
    {"success": True,  "result": ..., "error": None}   ← sukses
    {"success": False, "result": None, "error": "..."}  ← gagal
"""

from __future__ import annotations

from typing import Any


def ok(result: Any) -> dict[str, Any]:
    return {"success": True, "result": result, "error": None}


def fail(error: str) -> dict[str, Any]:
    return {"success": False, "result": None, "error": error}
