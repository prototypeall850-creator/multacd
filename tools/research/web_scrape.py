"""web_scrape — fetch konten URL, bersihkan jadi markdown. ASK-REQUIRED.

Lebih pintar dari web_fetch (Phase 1): hapus nav/ads/script, deteksi
paywall, convert ke markdown rapi. Strategi fallback:

  1. scraped  — konten penuh berhasil dibersihkan (terbaik)
  2. snippet  — scraping gagal/paywall, pakai ringkasan search engine
  3. failed   — tidak ada konten sama sekali (sumber di-skip di synthesis)

Gagal fetch BUKAN fail() — return ok() dengan content_source yang jujur,
supaya orchestrator research lanjut ke sumber berikutnya.

Test cepat:
    python -m tools.research.web_scrape
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as _md

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_scrape",
        "description": (
            "Ambil konten penuh URL sebagai markdown bersih (tanpa nav/ads). "
            "Kalau paywall atau gagal, return content_source snippet/failed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL yang mau di-scrape."},
                "timeout": {"type": "integer", "default": 15,
                            "description": "Batas waktu detik."},
                "snippet": {"type": "string", "default": "",
                            "description": "Ringkasan search engine (fallback kalau scrape gagal)."},
            },
            "required": ["url"],
        },
    },
}

MIN_CONTENT_CHARS = 200  # di bawah ini → dianggap paywall/kosong

_JUNK_SELECTORS = [
    "nav", "header", "footer", "aside", "script", "style", "noscript",
    "form", "iframe", ".ads", ".advertisement", ".sidebar", ".cookie-banner",
    ".cookie-consent", ".popup", ".modal", ".newsletter", ".share-buttons",
    ".related-posts", ".comments",
]
_PAYWALL_MARKERS = [
    "subscribe to read", "subscribe to continue", "sign in to read",
    "sign in to continue", "log in to continue", "premium content",
    "members only", "register to continue", "start your free trial",
    "you've reached your limit", "metered paywall",
]
_BLANK = re.compile(r"\n{3,}")


def clean_html(html: str) -> BeautifulSoup:
    """Parse + buang elemen sampah. Return soup siap convert."""
    soup = BeautifulSoup(html, "html.parser")
    # select() = CSS selector (mendukung nama tag DAN .class).
    # NOTE: soup([...]) tidak bisa — string dianggap nama tag semua.
    for tag in soup.select(", ".join(_JUNK_SELECTORS)):
        tag.decompose()
    # Elemen display:none (biasanya tracking/paywall nudge)
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        tag.decompose()
    return soup


def html_to_markdown(soup: BeautifulSoup) -> str:
    """Convert soup bersih → markdown. Jaga heading/link/code/table."""
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = _md(str(main), heading_style="ATX").strip()
    return _BLANK.sub("\n\n", text)


def detect_paywall(content: str) -> bool:
    """True kalau konten kependekan atau ada marker paywall."""
    if len(content.strip()) < MIN_CONTENT_CHARS:
        return True
    lowered = content.lower()
    return any(m in lowered for m in _PAYWALL_MARKERS)


def web_scrape(url: str, timeout: int = 15, snippet: str = "") -> dict[str, Any]:
    if not url.startswith(("http://", "https://")):
        return fail(f"URL harus http(s): {url}")
    try:
        resp = httpx.get(
            url, timeout=timeout, follow_redirects=True,
            headers={"User-Agent": "multacd/1.0 (+agentic-tui)"},
        )
        resp.raise_for_status()
    except httpx.TimeoutException:
        return _fallback(url, snippet, f"Timeout {timeout} dtk: {url}")
    except httpx.HTTPStatusError as e:
        return _fallback(url, snippet, f"HTTP {e.response.status_code}: {url}")
    except httpx.HTTPError as e:
        return _fallback(url, snippet, f"Gagal fetch {url}: {e}")
    ctype = resp.headers.get("content-type", "")
    if "html" not in ctype and "text" not in ctype:
        return _fallback(url, snippet, f"Bukan halaman web ({ctype}): {url}")

    soup = clean_html(resp.text)
    title = (soup.title.string.strip() if soup.title and soup.title.string
             else url)
    content = html_to_markdown(soup)
    if detect_paywall(content):
        return _fallback(url, snippet,
                         f"Paywall/konten terlalu pendek: {url}", title=title)
    return ok({"url": url, "title": title, "content": content,
               "content_source": "scraped", "error": None})


def _fallback(url: str, snippet: str, err: str,
              title: str = "") -> dict[str, Any]:
    """Gagal scrape: pakai snippet kalau ada, else failed. Tetap ok()."""
    if snippet.strip():
        return ok({"url": url, "title": title or url, "content": snippet,
                   "content_source": "snippet", "error": err})
    return ok({"url": url, "title": title or url, "content": "",
               "content_source": "failed", "error": err})


if __name__ == "__main__":
    # 1. clean_html buang sampah, pertahankan artikel
    sample = """
    <html><head><title>Judul Tes</title><style>.x{}</style></head>
    <body><nav>menu</nav><div class="ads">beli ini</div>
    <script>alert(1)</script><div class="cookie-banner">terima cookie</div>
    <article><h1>Halo</h1><p>Isi penting artikel yang cukup panjang. """ + \
        "x" * 300 + """</p></article>
    <footer>copyright</footer></body></html>"""
    soup = clean_html(sample)
    assert soup.find("nav") is None and soup.find("footer") is None
    assert soup.find("script") is None
    assert "beli ini" not in str(soup) and "terima cookie" not in str(soup)
    assert "Isi penting" in str(soup)

    # 2. html_to_markdown jaga heading
    md = html_to_markdown(soup)
    assert "# Halo" in md and "Isi penting" in md, md[:200]

    # 3. detect_paywall: pendek + marker
    assert detect_paywall("pendek")
    assert detect_paywall("x" * 300 + " subscribe to read more")
    assert not detect_paywall("konten normal yang panjang. " * 20)

    # 4. URL non-http → fail (validasi, bukan fallback)
    r = web_scrape("ftp://x.com")
    assert not r["success"] and "http" in r["error"], r

    # 5. Connection refused → fallback snippet / failed, tetap success=True
    r = web_scrape("http://127.0.0.1:9/tidak-ada", timeout=3,
                   snippet="ringkasan cadangan")
    assert r["success"] and r["result"]["content_source"] == "snippet", r
    assert r["result"]["content"] == "ringkasan cadangan"
    r = web_scrape("http://127.0.0.1:9/tidak-ada", timeout=3)
    assert r["success"] and r["result"]["content_source"] == "failed", r
    assert r["result"]["error"], r

    print("✅ web_scrape self-test OK (clean + paywall + fallback)")
