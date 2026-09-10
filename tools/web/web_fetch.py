"""web_fetch — fetch konten URL, return sebagai teks. ASK-REQUIRED."""

from __future__ import annotations

import html as html_lib
import re
from typing import Any

import httpx

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_fetch",
        "description": "Ambil konten URL dan kembalikan sebagai teks (HTML dibersihkan).",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "max_chars": {"type": "integer", "default": 30000},
                "timeout": {"type": "integer", "default": 30},
            },
            "required": ["url"],
        },
    },
}

_TAG_RE = re.compile(r"<(script|style|nav|footer)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG_ALL = re.compile(r"<[^>]+>")
_BLANK = re.compile(r"\n\s*\n+")


def _html_to_text(page: str) -> str:
    page = _TAG_RE.sub(" ", page)
    page = _TAG_ALL.sub(" ", page)
    text = html_lib.unescape(page)
    text = _BLANK.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def web_fetch(url: str, max_chars: int = 30000, timeout: int = 30) -> dict[str, Any]:
    if not url.startswith(("http://", "https://")):
        return fail(f"URL harus http(s): {url}")
    try:
        resp = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "multacd/1.0 (+agentic-tui)"},
        )
        resp.raise_for_status()
    except httpx.TimeoutException:
        return fail(f"Timeout {timeout} dtk: {url}")
    except httpx.HTTPStatusError as e:
        return fail(f"HTTP {e.response.status_code}: {url}")
    except httpx.HTTPError as e:
        return fail(f"Gagal fetch {url}: {e}")
    ctype = resp.headers.get("content-type", "")
    text = resp.text
    if "html" in ctype:
        text = _html_to_text(text)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n[...dipotong: > {max_chars} karakter...]"
    return ok(text or "(halaman kosong)")
