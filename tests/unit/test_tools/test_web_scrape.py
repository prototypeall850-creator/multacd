"""Unit: web_scrape — sukses dibersihkan, 404 pakai snippet fallback."""

from __future__ import annotations

import httpx

from tools.research.web_scrape import web_scrape


def _fake_ok(request: httpx.Request) -> httpx.Response:
    html = ("<html><body><article><h1>Judul</h1><p>" + "isi " * 100
            + "</p></article></body></html>")
    return httpx.Response(200, text=html,
                          headers={"content-type": "text/html"},
                          request=httpx.Request("GET", "https://contoh.test/a"))


def test_scrape_success(monkeypatch):
    import tools.research.web_scrape as mod

    monkeypatch.setattr(mod.httpx, "get",
                        lambda url, **kw: _fake_ok(None))  # type: ignore
    r = web_scrape("https://contoh.test/a")
    assert r["success"]
    assert r["result"]["content_source"] == "scraped"


def test_scrape_404_falls_back_to_snippet(monkeypatch):
    import tools.research.web_scrape as mod

    def _raise(url, **kw):
        raise mod.httpx.HTTPStatusError(
            "404", request=httpx.Request("GET", url),
            response=httpx.Response(404, text="x"))

    monkeypatch.setattr(mod.httpx, "get", _raise)
    r = web_scrape("https://contoh.test/hilang", snippet="ringkasan cadangan")
    assert r["success"]
    assert r["result"]["content_source"] in ("snippet", "failed")
