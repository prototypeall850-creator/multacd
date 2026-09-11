"""Cron scheduler engine — APScheduler + SQLite persist (PLAN Phase 4 §9).

Source of truth = tabel `jobs` milik sendiri (sync sqlite3 — aman dipanggil
dari tool sync via to_thread). Scheduler live (memory) mirror tabel saat
start; tool add/remove tulis tabel + live kalau daemon jalan.

Satu engine per proses via get_engine().

Test cepat:
    python -m scheduler.engine
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

JOB_ACTIONS = ("briefing", "research")
JOB_FUNC_REF = "scheduler.jobs:run_job"


def db_path() -> Path:
    """~/.multacd/jobs.db (hormati MULTACD_HOME buat isolasi test)."""
    return Path(os.environ.get("MULTACD_HOME", str(Path.home()))) / ".multacd" / "jobs.db"


def validate_cron(cron: str) -> tuple[bool, str]:
    """Return (True, '') atau (False, pesan_error)."""
    try:
        CronTrigger.from_crontab((cron or "").strip())
    except ValueError as e:
        return False, f"cron tidak valid {cron!r}: {e}"
    return True, ""


def next_run_str(cron: str) -> str:
    """Next fire 'YYYY-MM-DD HH:MM' atau '-' kalau gagal hitung."""
    try:
        nxt = CronTrigger.from_crontab(cron).get_next_fire_time(
            None, datetime.now())
    except Exception:
        return "-"
    return nxt.strftime("%Y-%m-%d %H:%M") if nxt else "-"


class SchedulerEngine:
    """Tabel SQLite + live scheduler (memory)."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or db_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_table()
        self.scheduler = AsyncIOScheduler()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def _init_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS jobs ("
                "name TEXT PRIMARY KEY, cron TEXT NOT NULL, "
                "action TEXT NOT NULL, topic TEXT NOT NULL DEFAULT '', "
                "channel TEXT NOT NULL DEFAULT 'telegram')")

    @property
    def running(self) -> bool:
        return bool(self.scheduler.running)

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start(paused=False)
        for job in self.list_jobs():  # mirror tabel → live
            self._add_live(job["name"], job["cron"], job["action"],
                           job["topic"], job["channel"])

    def shutdown(self, wait: bool = False) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)

    def _add_live(self, name: str, cron: str, action: str,
                  topic: str, channel: str) -> None:
        self.scheduler.add_job(
            JOB_FUNC_REF, CronTrigger.from_crontab(cron),
            id=name, replace_existing=True,
            kwargs={"action": action, "topic": topic, "channel": channel,
                    "cron": cron, "name": name})

    def add_job(self, name: str, cron: str, action: str,
                topic: str = "", channel: str = "telegram") -> None:
        """Tambah/ganti job (persist). Raise ValueError kalau tidak valid."""
        name = (name or "").strip()
        if not name:
            raise ValueError("name tidak boleh kosong.")
        ok, err = validate_cron(cron)
        if not ok:
            raise ValueError(err)
        if action not in JOB_ACTIONS:
            raise ValueError(f"action harus salah satu {list(JOB_ACTIONS)}.")
        cron = cron.strip()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (name, cron, action, topic, channel) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET cron=excluded.cron, "
                "action=excluded.action, topic=excluded.topic, "
                "channel=excluded.channel",
                (name, cron, action, topic, channel))
        if self.scheduler.running:
            self._add_live(name, cron, action, topic, channel)

    def remove_job(self, name: str) -> bool:
        """Hapus job. False kalau tidak ada."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM jobs WHERE name = ?", (name,))
            gone = cur.rowcount > 0
        if self.scheduler.running:
            with suppress(Exception):
                self.scheduler.remove_job(name)
        return gone

    def list_jobs(self) -> list[dict[str, Any]]:
        """Semua jobs + next run. Jalan tanpa start (baca tabel)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, cron, action, topic, channel FROM jobs "
                "ORDER BY name").fetchall()
        return [{"name": n, "cron": c, "action": a, "topic": t,
                 "channel": ch, "next_run": next_run_str(c)}
                for n, c, a, t, ch in rows]

    def load_from_config(self, config: Any) -> dict[str, list]:
        """Load schedules dari config.yaml. Return {loaded, skipped}."""
        loaded: list[str] = []
        skipped: list[str] = []
        for sched in getattr(config, "schedules", None) or []:
            try:
                self.add_job(sched.name, sched.cron, sched.action,
                             getattr(sched, "topic", "") or "",
                             getattr(sched, "channel", "") or "telegram")
                loaded.append(sched.name)
            except ValueError as e:
                print(f"⚠️ skip schedule {getattr(sched, 'name', '?')}: {e}")
                skipped.append(getattr(sched, "name", "?"))
        return {"loaded": loaded, "skipped": skipped}


_engine: SchedulerEngine | None = None


def get_engine() -> SchedulerEngine:
    """Singleton per proses (daemon + tool berbagi store yang sama)."""
    global _engine
    if _engine is None:
        _engine = SchedulerEngine()
    return _engine


def reset_engine() -> None:
    """Buang singleton (test ganti MULTACD_HOME di tengah jalan)."""
    global _engine
    if _engine is not None:
        with suppress(Exception):
            _engine.shutdown(wait=False)
    _engine = None


if __name__ == "__main__":
    import tempfile

    from core.config import Config as _Config

    with tempfile.TemporaryDirectory() as home:
        os.environ["MULTACD_HOME"] = home
        reset_engine()
        eng = SchedulerEngine()
        assert eng.list_jobs() == []

        eng.add_job("pagi", "0 7 * * *", "briefing")
        eng.add_job("senin", "0 9 * * MON", "research", topic="AI news")
        jobs = eng.list_jobs()
        assert [j["name"] for j in jobs] == ["pagi", "senin"]
        assert jobs[1]["topic"] == "AI news"
        assert jobs[0]["next_run"] > "2000", jobs[0]

        for bad in ("ngawur", "0 7 * *", ""):
            try:
                eng.add_job("x", bad, "briefing")
                raise AssertionError(f"harus tolak: {bad}")
            except ValueError:
                pass
        try:
            eng.add_job("x", "0 7 * * *", "email")
            raise AssertionError("harus tolak action")
        except ValueError:
            pass

        assert eng.remove_job("pagi") and not eng.remove_job("pagi")

        # Persist: engine baru lihat tabel yang sama (tanpa start).
        eng2 = SchedulerEngine()
        assert [j["name"] for j in eng2.list_jobs()] == ["senin"]

        # load_from_config: 1 valid + 1 skip.
        cfg = _Config(model="m", api_key="k", schedules=[
            {"name": "brief", "cron": "30 8 * * *", "action": "briefing"},
            {"name": "rusak", "cron": "kapan", "action": "briefing"},
        ])
        res = eng2.load_from_config(cfg)
        assert res["loaded"] == ["brief"] and res["skipped"] == ["rusak"], res
        reset_engine()
        del os.environ["MULTACD_HOME"]

    # Handler dispatcher (tanpa network).
    from scheduler.jobs import register_handler, run_job
    assert "belum tersedia" in str(run_job("email", name="t"))
    register_handler("demo", lambda **kw: f"ok:{kw['name']}")
    assert run_job("demo", name="t") == "ok:t"

    print("✅ scheduler self-test OK (cron + persist + config)")
