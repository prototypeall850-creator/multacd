"""schedule_job — tambah/ganti scheduled job. ASK-REQUIRED.

Tulis ke tabel SQLite (persist, survive restart). Daemon yang jalan
mirror ke live scheduler; kalau daemon mati, job aktif saat start.

Test cepat:
    python -m tools.personal.schedule_job
"""

from __future__ import annotations

from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "schedule_job",
        "description": ("Tambah/ganti job terjadwal (cron 5 field, "
                        "cth '0 7 * * *'). action: briefing | research."),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "cron": {"type": "string"},
                "action": {"type": "string", "default": "briefing"},
                "topic": {"type": "string", "default": "",
                           "description": "topik (wajib untuk research)"},
                "channel": {"type": "string", "default": "telegram"},
            },
            "required": ["name", "cron"],
        },
    },
}


def schedule_job(name: str, cron: str, action: str = "briefing",
                 topic: str = "", channel: str = "telegram") -> dict[str, Any]:
    from scheduler.engine import get_engine, next_run_str, validate_cron

    ok_cron, err = validate_cron(cron)
    if not ok_cron:
        return fail(err + " Contoh valid: '0 7 * * *', '0 9 * * MON'.")
    if action not in ("briefing", "research"):
        return fail("action harus 'briefing' atau 'research'.")
    if action == "research" and not (topic or "").strip():
        return fail("research butuh topic (cth: 'AI news minggu ini').")
    try:
        get_engine().add_job(name, cron, action, topic, channel)
    except ValueError as e:
        return fail(str(e))
    return ok(f"Job '{name.strip()}' terjadwal ({cron.strip()}) — "
              f"next: {next_run_str(cron)}.")


if __name__ == "__main__":
    import os
    import tempfile

    from scheduler.engine import reset_engine

    with tempfile.TemporaryDirectory() as home:
        os.environ["MULTACD_HOME"] = home
        reset_engine()
        r = schedule_job("pagi", "0 7 * * *", "briefing")
        assert r["success"], r
        r = schedule_job("x", "ngawur", "briefing")
        assert not r["success"] and "cron" in r["error"]
        r = schedule_job("x", "0 7 * * *", "research")
        assert not r["success"] and "topic" in r["error"]
        r = schedule_job("x", "0 7 * * *", "email")
        assert not r["success"] and "action" in r["error"]
        reset_engine()
        del os.environ["MULTACD_HOME"]

    print("✅ schedule_job self-test OK (validasi + tulis)")
