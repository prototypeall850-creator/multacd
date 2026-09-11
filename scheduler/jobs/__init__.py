"""Scheduled job handlers — dispatcher + registrasi (Phase 4).

Step 6: dispatcher + register_handler (handler asli diisi Step 7).
Step 7: briefing_job & research_job daftar via register_handler.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

HANDLERS: dict[str, Callable[..., Any]] = {}


def register_handler(action: str, func: Callable[..., Any]) -> None:
    """Daftarkan handler untuk action ('briefing' | 'research' | ...)."""
    HANDLERS[action] = func


def run_job(action: str, topic: str = "", channel: str = "telegram",
            cron: str = "", name: str = "") -> Any:
    """Fungsi yang direferensikan scheduler (string ref, persist di SQLite).

    Return hasil handler, atau pesan skip kalau handler belum terdaftar
    (misal DB lama jalan di build baru — jangan crash scheduler).
    """
    handler = HANDLERS.get(action)
    if handler is None:
        msg = f"skip job {name!r}: handler {action!r} belum tersedia"
        print(f"⚠️ {msg}")
        return msg
    return handler(topic=topic, channel=channel, cron=cron, name=name)


# Handler bawaan Step 7 — import di akhir (registrasi via _register()).
from scheduler.jobs import briefing_job as _briefing_job  # noqa: E402,F401
from scheduler.jobs import research_job as _research_job  # noqa: E402,F401
