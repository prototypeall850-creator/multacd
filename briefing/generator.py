"""Briefing generator — kumpul → filter privasi → narasi LLM → gabung.

cepat:
    python -m briefing.generator
"""

from __future__ import annotations

import datetime
from typing import Any

from briefing.privacy import PrivacyFilter
from briefing.sources.git_source import get_git_status
from briefing.sources.news_source import get_news_sync
from briefing.sources.todo_source import get_todos

_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
_BULAN = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
          "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

NARRATIVE_PROMPT = (
    "Buat briefing pagi yang ringkas dan informatif dari data berikut. "
    "Bahasa: Indonesia santai tapi informatif. "
    "Format: teks biasa untuk Telegram (tanpa markdown, tanpa header #). "
    "Fokus pada yang actionable.\n\nDATA:\n{data}")


def _today_str(today: datetime.date | None = None) -> str:
    today = today or datetime.date.today()
    return (f"{_HARI[today.weekday()]}, {today.day} "
            f"{_BULAN[today.month]} {today.year}")


def _collect_raw(cfg: Any, research_fn: Any = None,
                 todo_extra: Any = None, projects: Any = None) -> str:
    """Kumpulkan data mentah semua section yang aktif di config."""
    b = cfg.briefing
    blocks: list[str] = []
    if b.todo:
        todos = get_todos(todo_extra)
        blocks.append("TODO:\n" + ("\n".join(f"- {t}" for t in todos)
                                  if todos else "(tidak ada todo pending)"))
    if b.git_status:
        statuses = get_git_status(projects)
        blocks.append("GIT:\n" + ("\n".join(statuses)
                                  if statuses else "(tidak ada project)"))
    if b.news:
        topics = list(b.news_topics or [])
        if topics:
            news = get_news_sync(topics, research_fn, b.news_sources)
            lines = [f"[{t}] {news.get(t, '-')}" for t in topics]
            blocks.append("BERITA:\n" + "\n".join(lines))
    return "\n\n".join(blocks)


async def _narrate(llm: Any, clean: str) -> str:
    done = await llm.complete(
        [{"role": "user",
          "content": NARRATIVE_PROMPT.format(data=clean[:12000])}])
    return (done.text or "").strip() or "(LLM tidak memberi narasi)"


def generate_briefing(config: Any = None, llm: Any = None,
                      research_fn: Any = None,
                      todo_extra: Any = None, projects: Any = None,
                      today: datetime.date | None = None) -> str:
    """Generate teks briefing lengkap (sync — aman dari job thread)."""
    from tools.research.quick_research import _run_coro

    if config is None:
        from core.config import get_active_config, load_config
        config = get_active_config() or load_config()
    if llm is None:
        from core.llm_client import setup_client
        llm = setup_client(config)

    raw = _collect_raw(config, research_fn, todo_extra, projects)
    clean, private = PrivacyFilter().filter(raw)
    narrative = (_run_coro(_narrate(llm, clean)) if clean.strip()
                 else "(tidak ada data briefing hari ini)")
    parts = [f"Briefing Pagi — {_today_str(today)}", "", narrative]
    if private:
        parts += ["", "─────", "PRIVATE (tidak dikirim ke AI):",
                  *("- " + item for item in private)]
    return "\n".join(parts).strip()


if __name__ == "__main__":
    import os
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace

    from core.llm_client import StreamDone

    seen_prompts: list[str] = []

    class _FakeLLM:
        async def complete(self, messages: list) -> StreamDone:
            seen_prompts.append(messages[0]["content"])
            return StreamDone("Ringkasan: 2 todo, git bersih.", [])

    async def _fake_news(topic: str) -> str:
        return f"kabar {topic}: baik"

    with tempfile.TemporaryDirectory() as d:
        os.environ["MULTACD_HOME"] = d
        todo = Path(d) / "todo.md"
        todo.write_text("- Fix bug\n- [private] Password db: s3cr3t\n",
                        encoding="utf-8")
        cfg = SimpleNamespace(briefing=SimpleNamespace(
            todo=True, news=True, git_status=False, news_topics=["AI"],
            news_sources=3))
        out = generate_briefing(config=cfg, llm=_FakeLLM(),
                                research_fn=_fake_news,
                                todo_extra=[todo],
                                today=datetime.date(2026, 9, 11))
        assert "Briefing Pagi — Jumat, 11 Sep 2026" in out
        assert "Ringkasan" in out and "Fix bug" not in out.split("PRIVATE")[0]
        assert "s3cr3t" in out.split("PRIVATE")[1]  # private ada di akhir
        assert "s3cr3t" not in seen_prompts[0]  # TIDAK bocor ke LLM
        assert "kabar AI" in seen_prompts[0]  # berita masuk LLM
        del os.environ["MULTACD_HOME"]

    print("✅ generator self-test OK (narrate + privacy no-leak)")
