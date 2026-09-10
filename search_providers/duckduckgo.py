"""DuckDuckGo provider — endpoint HTML tidak resmi, tanpa API key.

Fallback terakhir: gratis tapi rapuh (rate limit, struktur HTML bisa
berubah sewaktu-waktu). Rekomendasikan Tavily kalau bisa.

Rate limit → retry dengan exponential backoff (3x percobaan).
"""

from __future__ import annotations

import html as html_lib
import re
import time
import urllib.parse

import httpx

from search_providers.base import SearchProvider, SearchProviderError, SearchResult

_ENDPOINT = "https://html.duckduckgo.com/html/"
_RESULT_RE = re.compile(
    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_SNIPPET_RE = re.compile(
    r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)


def _clean(text: str) -> str:
    text = _TAG_RE.sub(" ", text)
    return html_lib.unescape(re.sub(r"\s+", " ", text)).strip()


def _direct_url(href: str) -> str:
    """DDG membungkus link luar via //duckduckgo.com/l/?uddg=<encoded>."""
    href = html_lib.unescape(href)
    if "uddg=" in href:
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
            if qs.get("uddg"):
                return qs["uddg"][0]
        except ValueError:
            pass
    return href


def _parse_html(page: str) -> list[SearchResult]:
    """Parse halaman HTML DDG → SearchResult. Pure function."""
    out: list[SearchResult] = []
    links = _RESULT_RE.findall(page)
    snippets = _SNIPPET_RE.findall(page)
    for i, (href, title_html) in enumerate(links):
        url = _direct_url(href)
        if not url.startswith("http"):
            continue
        snippet = _clean(snippets[i]) if i < len(snippets) else ""
        out.append(SearchResult(
            title=_clean(title_html), url=url, snippet=snippet,
            score=max(0.0, 1.0 - i * 0.05),
        ))
    return out


class DuckDuckGoProvider(SearchProvider):
    def __init__(self, api_key: str = "") -> None:
        pass  # tanpa key — argumen diterima agar factory seragam

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = httpx.post(
                    _ENDPOINT,
                    data={"q": query},
                    headers={"User-Agent": "multacd/1.0 (+agentic-tui)"},
                    timeout=20, follow_redirects=True,
                )
                if resp.status_code in (202, 429):
                    raise SearchProviderError("rate-limit")
                resp.raise_for_status()
                return _parse_html(resp.text)[:num_results]
            except SearchProviderError as e:
                last_err = e
                time.sleep(2 ** attempt)  # backoff 1, 2, 4 dtk
            except httpx.TimeoutException as e:
                last_err = e
                time.sleep(2 ** attempt)
            except httpx.HTTPError as e:
                raise SearchProviderError(
                    f"DuckDuckGo HTTP error: {e}") from e
        raise SearchProviderError(
            f"DuckDuckGo rate limit / tidak bisa diakses setelah 3x coba "
            f"(terakhir: {last_err}). Coba lagi nanti atau pakai Tavily.")


if __name__ == "__main__":
    sample = """
    <a class="result__a" href="https://a.com/1"><b>Judul</b> A</a>
    <a class="result__snippet" href="x">snip A hehe</a>
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fb.com%2F2&amp;rut=x">Judul B</a>
    <a class="result__a" href="/internal">skip (bukan http)</a>
    """
    out = _parse_html(sample)
    assert len(out) == 2, out
    assert out[0].title == "Judul A" and out[0].snippet == "snip A hehe"
    assert out[1].url == "https://b.com/2", out[1].url
    assert out[0].score > out[1].score

    # Konstruksi tanpa key harus bisa (factory seragam)
    DuckDuckGoProvider(api_key="")
    print("✅ duckduckgo self-test OK (parse + uddg decode)")
