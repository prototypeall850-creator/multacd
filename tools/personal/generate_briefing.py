"""generate_briefing — buat briefing sekarang via agent. ASK-REQUIRED.

Bakar token LLM + bisa kirim ke Telegram, jadi selalu konfirmasi dulu.
send_to_admin=True → langsung kirim ke admin setelah generate.

Test cepat:
    python -m tools.personal.generate_briefing
"""

from __future__ import annotations

from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_briefing",
        "description": ("Generate daily briefing sekarang (todo + git + "
                        "berita). Opsi kirim ke admin Telegram."),
        "parameters": {
            "type": "object",
            "properties": {
                "send_to_admin": {"type": "boolean", "default": False,
                                  "description": "kirim hasil ke admin via bot"},
            },
        },
    },
}


def generate_briefing(send_to_admin: bool = False) -> dict[str, Any]:
    from briefing.generator import generate_briefing as _gen

    try:
        text = _gen()
    except SystemExit:
        return fail("Config belum ada — setup dulu.")
    except Exception as e:
        return fail(f"Gagal generate briefing ({type(e).__name__}): {e}")
    if send_to_admin:
        from tools.personal.send_telegram import send_telegram as _send
        res = _send(text, target="admin")
        if not res["success"]:
            return fail(f"Briefing jadi, tapi {res['error']}")
        return ok(text + "\n\n(✅ terkirim ke admin)")
    return ok(text)


if __name__ == "__main__":
    from briefing import generator as _gen_mod  # noqa: F401 (pasti ada)
    from core.llm_client import StreamDone

    seen: list[str] = []

    class _FakeLLM:
        async def complete(self, messages: list) -> StreamDone:
            seen.append(messages[0]["content"])
            return StreamDone("Ringkasan test.", [])

    _orig_setup = None
    import core.llm_client as _llm_mod
    _orig_setup = _llm_mod.setup_client
    _llm_mod.setup_client = lambda cfg: _FakeLLM()  # type: ignore
    try:
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as home:
            os.environ["MULTACD_HOME"] = home
            # Satu section aktif (todo) biar LLM kepanggil via mock.
            from pathlib import Path as _P
            _P(home, ".multacd").mkdir(parents=True, exist_ok=True)
            _P(home, ".multacd", "todo.md").write_text(
                "- Coba briefing\n", encoding="utf-8")
            # Minimal: tanpa todo/git/news (flag mati) → tanpa network.
            from types import SimpleNamespace
            _cfg = SimpleNamespace(briefing=SimpleNamespace(
                todo=True, news=False, git_status=False,
                news_topics=[], news_sources=3))
            from core.config import set_active_config as _set
            _set(_cfg)  # type: ignore
            try:
                r = generate_briefing()
                assert r["success"] and "Ringkasan test" in r["result"], r
            finally:
                _set(None)
            del os.environ["MULTACD_HOME"]
    finally:
        _llm_mod.setup_client = _orig_setup

    print("✅ generate_briefing self-test OK (mock LLM)")
