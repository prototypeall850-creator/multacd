"""Briefing job — dipanggil scheduler saat jadwal tiba (PLAN Phase 4 Step 7).

Generate briefing lalu kirim ke admin via send_telegram.
Return ringkasan hasil (masuk log scheduler).

Test cepat:
    python -m scheduler.jobs.briefing_job
"""

from __future__ import annotations


def briefing_job(topic: str = "", channel: str = "telegram",
                 cron: str = "", name: str = "") -> str:
    from briefing.generator import generate_briefing
    from tools.personal.send_telegram import send_telegram

    text = generate_briefing()
    res = send_telegram(text, target="admin")
    if res["success"]:
        return f"briefing {name!r} terkirim ke admin."
    return f"briefing {name!r} gagal kirim: {res['error']}"


def _register() -> None:
    from scheduler.jobs import register_handler
    register_handler("briefing", briefing_job)


_register()


if __name__ == "__main__":
    from scheduler.jobs import HANDLERS
    assert HANDLERS.get("briefing") is briefing_job
    print("✅ briefing_job self-test OK (terdaftar)")
