"""Research job — riset terjadwal lalu kirim ke admin (PLAN Phase 4 Step 7).

Dipakai schedule action='research' + topic. Berat? pakai quick_research
(tool sync yang sudah ada — active config + bridge internal).

Test cepat:
    python -m scheduler.jobs.research_job
"""

from __future__ import annotations


def research_job(topic: str = "", channel: str = "telegram",
                 cron: str = "", name: str = "") -> str:
    from tools.personal.send_telegram import send_telegram
    from tools.research.quick_research import quick_research as _qr

    if not (topic or "").strip():
        return f"research {name!r}: topic kosong, skip."
    res = _qr(topic.strip())
    if not res["success"]:
        return f"research {name!r} gagal: {res['error']}"
    answer = (res["result"] or {}).get("answer", "(kosong)")
    sent = send_telegram(f"Hasil riset terjadwal: {topic}\n\n{answer}",
                         target="admin")
    if sent["success"]:
        return f"research {name!r} terkirim ke admin."
    return f"research {name!r} gagal kirim: {sent['error']}"


def _register() -> None:
    from scheduler.jobs import register_handler
    register_handler("research", research_job)


_register()


if __name__ == "__main__":
    from scheduler.jobs import HANDLERS
    assert HANDLERS.get("research") is research_job
    assert "topic kosong" in research_job(topic="  ", name="t")
    print("✅ research_job self-test OK (terdaftar + guard)")
