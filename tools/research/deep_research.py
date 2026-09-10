"""deep_research tool — riset mendalam multi-round. ASK-REQUIRED.

Laporan lengkap 2-5 menit: round makin dalam, cross-reference,
deteksi kontradiksi. Wrapper sync di atas orchestrator (async),
jembatan _run_coro dipakai ulang dari quick_research.

Test cepat:
    python -m tools.research.deep_research
"""

from __future__ import annotations

from typing import Any

from tools.common import fail, ok
from tools.research.quick_research import _run_coro

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "deep_research",
        "description": (
            "Riset mendalam multi-round (2-5 menit): gali topik dari berbagai "
            "sudut, cross-reference sumber, flag kontradiksi, hasilkan laporan "
            "lengkap. Untuk jawaban cepat, pakai quick_research."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string",
                          "description": "Topik yang mau diriset mendalam."},
                "max_rounds": {"type": "integer", "default": 5,
                               "description": "Max round (1-10, default dari config)."},
                "language": {"type": "string", "default": "",
                             "description": "Bahasa output (kosong = ikuti bahasa pertanyaan)."},
            },
            "required": ["topic"],
        },
    },
}


def deep_research(topic: str, max_rounds: int = 5,
                  language: str = "") -> dict[str, Any]:
    if not (topic or "").strip():
        return fail("Topik riset tidak boleh kosong.")
    try:
        max_rounds = max(1, min(int(max_rounds or 5), 10))
    except (TypeError, ValueError):
        return fail("max_rounds harus angka 1-10.")
    try:
        from core.config import get_active_config, load_config
        from core.llm_client import setup_client
        from core.research.orchestrator import deep_research as _dr

        # Active config sesi (Bug 3) — hormati --config & /model; fallback
        # load_config() untuk pemakaian standalone (CLI/test tanpa TUI).
        config = get_active_config() or load_config()
        llm = setup_client(config)
        from core.research.bus import get_research_sink
        res = _run_coro(_dr(topic.strip(), max_rounds=max_rounds,
                            config=config, llm=llm,
                            language=(language or "").strip(),
                            on_event=get_research_sink()))
    except SystemExit:
        return fail(
            "Config belum disetup — jalankan `python main.py` sekali untuk "
            "melihat contoh config, lalu isi model + api_key + search_api_key.")
    except Exception as e:
        return fail(f"Deep research gagal ({type(e).__name__}): {e}")
    return ok(res.to_dict())


if __name__ == "__main__":
    import sys as _sys

    # 1. Topik kosong → fail
    r = deep_research("   ")
    assert not r["success"] and "kosong" in r["error"], r

    # 2. max_rounds ngawur → fail / clamp
    r = deep_research("t", max_rounds="banyak")  # type: ignore[arg-type]
    assert not r["success"] and "max_rounds" in r["error"], r

    # 3. Full tool dengan orchestrator mock (pola sys.modules[__name__],
    #    lihat NOTE anti-mock-nyasar di quick_research)
    from core.research.orchestrator import DeepResult

    _mod = _sys.modules[__name__]

    async def _fake_dr(topic: str, **kwargs: Any) -> DeepResult:
        assert kwargs.get("max_rounds") == 2, kwargs
        assert kwargs.get("language") == "Indonesia", kwargs
        return DeepResult(report="laporan mock",
                          sources=[], rounds=[{"round": 1}])

    _orig_run = _mod._run_coro
    from types import SimpleNamespace as _NS

    import core.config as _core_cfg
    import core.llm_client as _core_llm

    _orig_load, _orig_setup = _core_cfg.load_config, _core_llm.setup_client
    _core_cfg.load_config = lambda *a, **k: _NS(model="m", api_key="k")
    _core_llm.setup_client = lambda cfg: _NS(model="m")

    def _fake_runner(coro: Any) -> Any:
        import asyncio as _asyncio

        coro.close()
        return _asyncio.run(_fake_dr("t", max_rounds=2, language="Indonesia"))

    _mod._run_coro = _fake_runner
    try:
        r = deep_research("topik", max_rounds=2, language="Indonesia")
    finally:
        _mod._run_coro = _orig_run
        _core_cfg.load_config = _orig_load
        _core_llm.setup_client = _orig_setup
    assert r["success"] and r["result"]["report"] == "laporan mock", r
    assert r["result"]["rounds"] == [{"round": 1}]

    # 4. Active config menang atas load_config (fix Bug 3)
    # Patch orchestrator.deep_research langsung (import di dalam fungsi
    # terjadi saat call, jadi patch ini pasti kena).
    import core.research.orchestrator as _orch
    from core.config import set_active_config

    _active = _NS(model="model-aktif", api_key="k")
    set_active_config(_active)
    try:
        _seen_cfg: list = []

        async def _cfg_dr(topic: str, **kwargs: Any) -> DeepResult:
            _seen_cfg.append(kwargs.get("config"))
            return DeepResult(report="x", sources=[], rounds=[])

        _orig_dr = _orch.deep_research
        _orch.deep_research = _cfg_dr
        try:
            r = deep_research("topik")
        finally:
            _orch.deep_research = _orig_dr
        assert r["success"] and _seen_cfg and _seen_cfg[0] is _active, r
    finally:
        set_active_config(None)

    print("✅ deep_research tool self-test OK (validasi + mock)")
