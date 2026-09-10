"""web_search — cari via provider yang dikonfigurasi. AUTO-APPROVED.

Search saja, tidak akses konten halaman — aman tanpa konfirmasi.
Return list SearchResult (tanpa scraping dulu); konten penuh menyusul
via web_scrape / orchestrator research.

Provider + key diambil dari config; bisa dioverride via param eksplisit
(dipakai test & orchestrator).

Test cepat:
    python -m tools.research.web_search
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from search_providers.base import SearchProviderError
from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Cari informasi di internet via search provider yang dikonfigurasi. "
            "Return judul + URL + snippet (konten penuh via web_scrape)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "Kata kunci pencarian."},
                "num_results": {"type": "integer", "default": 5,
                                "description": "Jumlah hasil (1-20)."},
            },
            "required": ["query"],
        },
    },
}


def _resolve_provider(search_provider: str = "",
                      search_api_key: str = "") -> tuple[Any, str | None]:
    """Return (provider, error). Config file dibaca hanya kalau tidak dioverride."""
    from search_providers import get_provider

    if search_provider.strip():
        # Override eksplisit (test/orchestrator) — tanpa sentuh config file.
        cfg = SimpleNamespace(search_provider=search_provider,
                              search_api_key=search_api_key)
        try:
            return get_provider(cfg), None
        except Exception as e:
            return None, str(e)
    try:
        from core.config import get_active_config, load_config
        # Active config sesi (Bug 3) — hormati --config & /model.
        cfg = get_active_config() or load_config()
    except SystemExit:
        return None, (
            "Search provider belum disetup. Tambah `search_provider` dan "
            "`search_api_key` di ~/.multacd/config.yaml "
            "(atau pakai search_provider duckduckgo yang gratis).")
    except Exception as e:
        return None, f"Gagal baca config: {e}"
    try:
        return get_provider(cfg), None
    except Exception as e:
        return None, str(e)


def web_search(query: str, num_results: int = 5,
               search_provider: str = "",
               search_api_key: str = "") -> dict[str, Any]:
    if not query.strip():
        return fail("Query pencarian tidak boleh kosong.")
    num_results = max(1, min(int(num_results or 5), 20))
    provider, err = _resolve_provider(search_provider, search_api_key)
    if provider is None:
        return fail(err or "Provider search tidak tersedia.")
    try:
        results = provider.search(query.strip(), num_results=num_results)
    except SearchProviderError as e:
        return fail(str(e))
    except Exception as e:
        return fail(f"Search gagal ({type(e).__name__}): {e}")
    return ok({"query": query.strip(),
               "results": [r.to_dict() for r in results],
               "count": len(results)})


if __name__ == "__main__":
    import tempfile

    from search_providers.base import SearchResult

    # 1. Query kosong → fail
    r = web_search("   ")
    assert not r["success"] and "kosong" in r["error"], r

    # 2. Provider asing via override → fail jelas, tanpa sentuh network/config
    r = web_search("x", search_provider="google")
    assert not r["success"] and "tidak dikenal" in r["error"].lower(), r

    # 3. Key kosong (tavily) → fail jelas
    r = web_search("x", search_provider="tavily", search_api_key="")
    assert not r["success"] and "search_api_key" in r["error"], r

    # 4. Mock provider → format konsisten, tanpa network
    fake = [SearchResult(title="A", url="https://a.com/1", snippet="s",
                         score=0.9, content="isi", scraped=True)]
    import search_providers
    orig = search_providers.get_provider
    search_providers.get_provider = lambda cfg: (
        type("F", (), {"search": lambda self, q, num_results=5: fake})())
    try:
        r = web_search("topik", num_results=5,
                       search_provider="tavily", search_api_key="k")
    finally:
        search_providers.get_provider = orig
    assert r["success"] and r["result"]["count"] == 1, r
    assert r["result"]["results"][0]["url"] == "https://a.com/1"
    assert r["result"]["query"] == "topik"

    # 5. Tanpa config file → pesan setup yang jelas.
    # NOTE: CONFIG_DIR dievaluasi saat import, jadi isolasi via subprocess
    # tidak bisa in-process — patch DEFAULT_CONFIG_PATH ke path yang
    # tidak ada (resolve_config_path baca global ini saat dipanggil).
    tmp = tempfile.mkdtemp(prefix="multacd-nosetup-")
    import core.config as _cfg
    _orig_path = _cfg.DEFAULT_CONFIG_PATH
    _cfg.DEFAULT_CONFIG_PATH = _cfg.Path(tmp) / "config.yaml"
    try:
        r = web_search("x")
        assert not r["success"] and "belum disetup" in r["error"], r
    finally:
        _cfg.DEFAULT_CONFIG_PATH = _orig_path

    # 6. num_results di-clamp 1..20 (via mock, tanpa network)
    seen: dict = {}
    import search_providers as _sp
    _orig = _sp.get_provider
    _sp.get_provider = lambda cfg: (
        type("G", (), {"search": lambda self, q, num_results=5: (
            seen.update(n=num_results) or [])})())
    try:
        web_search("x", num_results=99, search_provider="t", search_api_key="k")
        assert seen["n"] == 20, seen
        web_search("x", num_results=0, search_provider="t", search_api_key="k")
        assert seen["n"] == 5, seen
    finally:
        _sp.get_provider = _orig

    # 7. Active config menang atas load_config (fix Bug 3)
    from core.config import set_active_config

    _active = SimpleNamespace(search_provider="tavily", search_api_key="k-aktif")
    set_active_config(_active)
    try:
        _seen: list = []
        import search_providers as _sp2
        _orig2 = _sp2.get_provider
        _sp2.get_provider = lambda cfg: (
            _seen.append(cfg) or
            type("H", (), {"search": lambda self, q, num_results=5: []})())
        try:
            r = web_search("x")
        finally:
            _sp2.get_provider = _orig2
        assert r["success"] and _seen and _seen[0] is _active, r
    finally:
        set_active_config(None)

    print("✅ web_search self-test OK (validasi + mock + no-config)")
