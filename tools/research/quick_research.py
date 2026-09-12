"""quick_research tool — riset cepat 1 round ala Perplexity. ASK-REQUIRED.

Akses internet + bakar token LLM → selalu konfirmasi dulu.
Wrapper sync di atas core.research.orchestrator (async).

Jembatan sync/async (_run_coro): jalan baik dari konteks sync (test,
CLI) maupun di dalam event loop yang sudah jalan (agent_loop) — kasus
kedua dieksekusi di thread terpisah dengan loop sendiri.

Test cepat:
    python -m tools.research.quick_research
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "quick_research",
        "description": (
            "Riset cepat satu topik dari internet (~30 detik): generate queries, "
            "search + baca sumber, synthesis jawaban berkutipan. "
            "Untuk topik kompleks butuh laporan mendalam, pakai deep_research."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string",
                          "description": "Topik atau pertanyaan yang mau diriset."},
                "language": {"type": "string", "default": "",
                             "description": "Bahasa output (kosong = ikuti bahasa pertanyaan)."},
            },
            "required": ["topic"],
        },
    },
}


def _run_coro(coro: Any) -> Any:
    """Jalankan coroutine dari konteks sync ATAU dalam loop yang jalan.

    Pool thread tidak mewarisi contextvars sendiri — context pemanggil
    (termasuk research sink task ini, R6) di-copy eksplisit biar
    on_event tetap sampai ke sesi yang benar.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import contextvars as _ctxvars
    ctx = _ctxvars.copy_context()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(ctx.run, asyncio.run, coro).result()


def quick_research(topic: str, language: str = "") -> dict[str, Any]:
    if not (topic or "").strip():
        return fail("Topik riset tidak boleh kosong.")
    try:
        from core.config import get_active_config, load_config
        from core.llm_client import setup_client
        from core.research.orchestrator import quick_research as _qr

        # Active config sesi (Bug 3) — hormati --config & /model; fallback
        # load_config() untuk pemakaian standalone (CLI/test tanpa TUI).
        config = get_active_config() or load_config()
        llm = setup_client(config)
        from core.research.bus import get_research_sink
        res = _run_coro(_qr(topic.strip(), config=config, llm=llm,
                            language=(language or "").strip(),
                            on_event=get_research_sink()))
    except SystemExit:
        return fail(
            "Config belum disetup — jalankan `python main.py` sekali untuk "
            "melihat contoh config, lalu isi model + api_key + search_api_key.")
    except Exception as e:
        return fail(f"Quick research gagal ({type(e).__name__}): {e}")
    return ok(res.to_dict())


if __name__ == "__main__":
    # 1. Topik kosong → fail (tanpa sentuh config/LLM)
    r = quick_research("   ")
    assert not r["success"] and "kosong" in r["error"], r

    # 2. _run_coro dari konteks sync
    async def _tambah(a: int, b: int) -> int:
        await asyncio.sleep(0)
        return a + b

    assert _run_coro(_tambah(2, 3)) == 5

    # 3. _run_coro dari DALAM loop yang jalan (simulasi agent_loop:
    #    konteks async memanggil tool sync yang membungkus coroutine)
    async def _dalam_loop() -> int:
        return _run_coro(_tambah(4, 5))

    assert asyncio.run(_dalam_loop()) == 9

    # 4. Full tool dengan orchestrator mock (tanpa network/LLM asli).
    # NOTE: patch via sys.modules[__name__] — file ini jalan sebagai
    # __main__ di bawah `python -m`, re-import by path bikin salinan
    # modul kedua dan mock nyasar (pernah bikin test nyangkut di flow asli).
    import sys as _sys

    from core.research.orchestrator import QuickResult

    _mod = _sys.modules[__name__]

    async def _fake_qr(topic: str, **kwargs: Any) -> QuickResult:
        assert kwargs.get("language") == "Indonesia", kwargs
        return QuickResult(answer="jawaban mock", sources=[], queries=["q1"])

    _orig = _mod._run_coro
    from types import SimpleNamespace as _NS

    import core.config as _core_cfg
    import core.llm_client as _core_llm

    _orig_load, _orig_setup = _core_cfg.load_config, _core_llm.setup_client
    _core_cfg.load_config = lambda *a, **k: _NS(model="m", api_key="k")
    _core_llm.setup_client = lambda cfg: _NS(model="m")
    _mod._run_coro = lambda coro: (coro.close(), asyncio.run(
        _fake_qr("t", language="Indonesia")))[1]
    try:
        # load_config + setup_client dimock → jalan tanpa config asli/LLM.
        r = quick_research("topik", language="Indonesia")
    finally:
        _mod._run_coro = _orig
        _core_cfg.load_config = _orig_load
        _core_llm.setup_client = _orig_setup
    assert r["success"] and r["result"]["answer"] == "jawaban mock", r
    assert r["result"]["queries"] == ["q1"]

    # 5. Active config menang atas load_config (fix Bug 3)
    # Patch orchestrator.quick_research langsung (import di dalam fungsi
    # terjadi saat call, jadi patch ini pasti kena).
    import core.research.orchestrator as _orch
    from core.config import set_active_config

    _active = _NS(model="model-aktif", api_key="k")
    set_active_config(_active)
    try:
        _seen_cfg: list = []

        async def _cfg_qr(topic: str, **kwargs: Any) -> QuickResult:
            _seen_cfg.append(kwargs.get("config"))
            return QuickResult(answer="x", sources=[], queries=[])

        _orig_qr = _orch.quick_research
        _orch.quick_research = _cfg_qr
        try:
            r = quick_research("topik")
        finally:
            _orch.quick_research = _orig_qr
        assert r["success"] and _seen_cfg and _seen_cfg[0] is _active, r
    finally:
        set_active_config(None)

    print("✅ quick_research tool self-test OK (validasi + bridge + mock)")
