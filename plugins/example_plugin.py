# contoh plugin multacd — copy ke ~/.multacd/plugins/ lalu start ulang.
# File ini sendiri TIDAK auto-load (folder repo), cuma template.
# Yang di-load: ~/.multacd/plugins/*.py
#
# Kontrak return tool (wajib):
#   {"success": True, "result": ..., "error": None}   ← sukses
#   {"success": False, "result": None, "error": "..."} ← gagal
# Pakai tools.common.ok() / fail() kalau mau konsisten.

"""Contoh plugin: waktu lokal + cuaca dummy (tanpa network)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

# ── Metadata (WAJIB: PLUGIN_NAME + TOOL_DEFINITIONS) ──
PLUGIN_NAME = "contoh"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = "Contoh plugin: waktu lokal dan cuaca dummy"
PLUGIN_AUTHOR = "kamu"

# ── Schema tool (format OpenAI function calling, WAJIB) ──
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "waktu_sekarang",
            "description": "Jam & tanggal sekarang (waktu lokal mesin).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cuaca_dummy",
            "description": "Contoh tool berparameter (dummy, tanpa API).",
            "parameters": {
                "type": "object",
                "properties": {
                    "kota": {"type": "string",
                             "description": "Nama kota (cth: Jakarta)."},
                },
                "required": ["kota"],
            },
        },
    },
]

# ── Permission per tool ("auto" langsung jalan, "ask" konfirmasi dulu).
# Tool yang tidak disebut di sini default "ask" (aman).
TOOL_PERMISSIONS = {
    "waktu_sekarang": "auto",
    "cuaca_dummy": "auto",
}


# ── Implementasi (nama fungsi HARUS sama dengan function.name) ──
def waktu_sekarang() -> dict[str, Any]:
    now = datetime.now().strftime("%A, %d %B %Y %H:%M")
    return {"success": True, "result": now, "error": None}


def cuaca_dummy(kota: str) -> dict[str, Any]:
    return {"success": True,
            "result": f"(dummy) {kota}: cerah 30°C — sambungkan API cuaca asli di sini.",
            "error": None}
