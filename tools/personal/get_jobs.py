"""get_jobs — lihat semua scheduled jobs. AUTO-APPROVED.

Test cepat:
    python -m tools.personal.get_jobs
"""

from __future__ import annotations

from typing import Any

from tools.common import ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_jobs",
        "description": "Tampilkan semua scheduled jobs + next run.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def get_jobs() -> dict[str, Any]:
    from scheduler.engine import get_engine

    jobs = get_engine().list_jobs()
    if not jobs:
        return ok("(tidak ada scheduled job)")
    lines = [f"- {j['name']}: {j['cron']} → {j['action']}"
             + (f" [{j['topic']}]" if j["topic"] else "")
             + f" (next: {j['next_run']})" for j in jobs]
    return ok("\n".join(lines))


if __name__ == "__main__":
    import os
    import tempfile

    from scheduler.engine import reset_engine
    from tools.personal.schedule_job import schedule_job

    with tempfile.TemporaryDirectory() as home:
        os.environ["MULTACD_HOME"] = home
        reset_engine()
        assert get_jobs()["result"] == "(tidak ada scheduled job)"
        assert schedule_job("pagi", "0 7 * * *", "briefing")["success"]
        r = get_jobs()
        assert "pagi" in r["result"] and "0 7 * * *" in r["result"], r
        reset_engine()
        del os.environ["MULTACD_HOME"]

    print("✅ get_jobs self-test OK (kosong + isi)")
