"""LLM client — wrapper provider native: streaming + tool call + retry.

Backend: core/providers (OpenAI-compatible + Anthropic via httpx).
Tanpa LiteLLM — ringan buat Termux (tanpa kompilasi Rust).

Dipakai oleh agent loop (Step 7) lewat async generator:

    client = setup_client(config)
    async for event in client.stream_completion(messages, tools):
        if isinstance(event, StreamText):
            ... tampilkan event.content ...
        elif isinstance(event, StreamDone):
            ... event.text = teks penuh, event.tool_calls = [...] ...

Test cepat tanpa API key (mock httpx, tanpa network):
    python -m core.llm_client
Test live (butuh ~/.multacd/config.yaml yang valid):
    python -m core.llm_client --live "hello"
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from core.config import Config, load_config
from core.providers import (
    ProviderAuthError,
    ProviderConnectionError,
    ProviderError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    resolve_provider,
)

MAX_CONNECTION_RETRIES = 3
MAX_RATE_LIMIT_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # detik, exponential backoff
REQUEST_TIMEOUT = 120.0


class LLMError(Exception):
    """Error LLM dengan pesan yang friendly — tampilkan langsung ke user."""


@dataclass
class ToolCallRequest:
    """Satu tool call yang diminta LLM (sudah dirakit dari fragment streaming)."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class StreamText:
    """Potongan teks baru dari LLM (tampilkan real-time ke TUI)."""

    content: str


@dataclass
class StreamDone:
    """Stream selesai: teks penuh + daftar tool call (bisa kosong).

    Token diisi dari chunk `usage` provider (resmi, bukan estimasi).
    0 = provider tidak melapor (streamingบาง provider tak kirim usage).
    """

    text: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0  # estimasi lokal (tabel harga provider)


StreamEvent = StreamText | StreamDone


def setup_client(config: Config) -> LLMClient:
    """Init client dari config (LiteLLM stateless — ini bungkus kwargs + retry)."""
    return LLMClient(config)


class LLMClient:
    def __init__(self, config: Config) -> None:
        self.config = config

    async def stream_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Kirim messages ke LLM, yield StreamText lalu diakhiri satu StreamDone.

        Routing provider by config.model (lihat resolve_provider).
        Retry hanya dilakukan jika stream BELUM menghasilkan teks apapun
        (aman — tidak ada duplikasi output). Gagal di tengah stream
        langsung raise LLMError.
        """
        try:
            spec = resolve_provider(self.config.model, self.config.api_base)
        except ProviderError as e:
            raise LLMError(str(e)) from e
        if spec.kind == "anthropic":
            from core.providers.anthropic import stream_chat
        else:
            from core.providers.openai_compat import stream_chat

        conn_attempts = 0
        rate_attempts = 0
        while True:
            yielded_any_text = False
            try:
                async for event in stream_chat(
                        spec, self.config.api_key, messages, tools,
                        self.config.max_tokens, self.config.temperature,
                        REQUEST_TIMEOUT):
                    if isinstance(event, StreamText) and event.content:
                        yielded_any_text = True
                    yield event
                return
            except ProviderRateLimitError as e:
                rate_attempts += 1
                if rate_attempts > MAX_RATE_LIMIT_RETRIES or yielded_any_text:
                    raise LLMError(
                        "Rate limit dari provider (429) — "
                        f"sudah retry {MAX_RATE_LIMIT_RETRIES}x, masih dibatasi. "
                        "Tunggu sebentar lalu coba lagi."
                    ) from e
                await asyncio.sleep(RETRY_BASE_DELAY * (2 ** (rate_attempts - 1)))
            except ProviderConnectionError as e:
                conn_attempts += 1
                if conn_attempts > MAX_CONNECTION_RETRIES or yielded_any_text:
                    raise LLMError(
                        "Gagal konek ke LLM provider "
                        f"({MAX_CONNECTION_RETRIES}x percobaan). "
                        "Cek koneksi internet / api_base di config."
                    ) from e
                await asyncio.sleep(RETRY_BASE_DELAY * conn_attempts)
            except ProviderAuthError as e:
                raise LLMError(
                    "API key ditolak provider. Cek `api_key` di ~/.multacd/config.yaml "
                    "(BYOK — pastikan key cocok dengan `model` yang dipilih)."
                ) from e
            except ProviderNotFoundError as e:
                raise LLMError(
                    f"Model `{self.config.model}` tidak ditemukan oleh provider. "
                    "Cek penulisan `model` di config (cth: "
                    "`anthropic/claude-sonnet-4-6`, `openai/gpt-4o`)."
                ) from e
            except LLMError:
                raise
            except ProviderError as e:
                raise LLMError(f"LLM error ({type(e).__name__}): {e}") from e
            except Exception as e:
                raise LLMError(f"LLM error tak terduga ({type(e).__name__}): {e}") from e

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> StreamDone:
        """Non-streaming: kumpulkan stream jadi satu hasil (buat test/debug)."""
        full: StreamDone | None = None
        async for event in self.stream_completion(messages, tools):
            if isinstance(event, StreamDone):
                full = event
        assert full is not None
        return full


# ── Self-test tanpa network (mock httpx stream) ────────────────────────────

class _FakeSSE:
    """Resp SSE palsu: aiter_lines + aread + status_code."""

    def __init__(self, lines: list[str], status: int = 200,
                 body: bytes = b"") -> None:
        self._lines = lines
        self.status_code = status
        self._body = body

    async def aiter_lines(self):  # type: ignore[no-untyped-def]
        for ln in self._lines:
            yield ln

    async def aread(self) -> bytes:
        return self._body


class _FakeCtx:
    def __init__(self, resp: _FakeSSE) -> None:
        self._resp = resp

    async def __aenter__(self) -> _FakeSSE:
        return self._resp

    async def __aexit__(self, *a: Any) -> None:
        return None


class _FakeClient:
    """Pengganti httpx.AsyncClient buat test (tanpa network)."""

    def __init__(self, resp: _FakeSSE) -> None:
        self._resp = resp
        self.seen: dict[str, Any] = {}

    def stream(self, method: str, url: str, **kw: Any) -> _FakeCtx:
        self.seen = {"method": method, "url": url, **kw}
        return _FakeCtx(self._resp)

    async def aclose(self) -> None:
        pass


def _sse_text(*chunks: str, usage: dict[str, int] | None = None) -> list[str]:
    import json as _json
    lines = [f"data: {_json.dumps({'choices': [{'delta': {'content': c}}]})}"
             for c in chunks]
    if usage is not None:
        lines.append(f"data: {_json.dumps({'usage': usage})}")
    lines.append("data: [DONE]")
    return lines


async def _self_test() -> None:
    from unittest.mock import patch as _patch

    import httpx as _httpx

    # ANTI-TRAP: file ini jalan sebagai __main__ saat `python -m`, sementara
    # adapter import `core.llm_client` terpisah (objek class ganda!).
    # Semua isinstance di test ini WAJIB pakai salinan kanonis itu.
    import core.llm_client as _canon

    cfg = Config(model="openai/gpt-4o", api_key="sk-x")
    client = LLMClient(cfg)

    async def _drain(c: LLMClient) -> StreamDone:
        async for ev in c.stream_completion([{"role": "user", "content": "hi"}]):
            if isinstance(ev, _canon.StreamDone):
                return ev
        raise AssertionError("unreachable")

    def _client_for(resp: _FakeSSE) -> Any:
        fake = _FakeClient(resp)
        return _patch("httpx.AsyncClient", return_value=fake), fake

    # 1. Teks streaming utuh + usage menempel
    lines = _sse_text("Halo, ", "dunia!",
                      usage={"prompt_tokens": 120, "completion_tokens": 30})
    p, fake = _client_for(_FakeSSE(lines))
    with p:
        done = await _drain(client)
    assert done.text == "Halo, dunia!" and done.tool_calls == [], done
    assert (done.prompt_tokens, done.completion_tokens) == (120, 30), done
    assert done.cost_usd > 0  # gpt-4o ada harga
    assert fake.seen["url"] == "https://api.openai.com/v1/chat/completions"
    assert fake.seen["json"]["model"] == "gpt-4o"

    # 2. Tool call terpecah + tanpa usage → 0
    import json as _json
    _half = _json.dumps({"command": "ls"})
    _frag1 = {"choices": [{"delta": {"tool_calls": [
        {"index": 0, "id": "c1",
         "function": {"name": "bash", "arguments": _half[:14]}}]}}]}
    _frag2 = {"choices": [{"delta": {"tool_calls": [
        {"index": 0, "function": {"arguments": _half[14:]}}]}}]}
    lines = [f"data: {_json.dumps(_frag1)}",
             f"data: {_json.dumps(_frag2)}", "data: [DONE]"]
    p, _ = _client_for(_FakeSSE(lines))
    with p:
        done = await _drain(client)
    assert len(done.tool_calls) == 1, done.tool_calls
    assert done.tool_calls[0].arguments == {"command": "ls"}, done.tool_calls[0]
    assert done.prompt_tokens == 0 and done.cost_usd == 0.0

    # 3. Auth error → LLMError (pesan sama kayak dulu)
    p, _ = _client_for(_FakeSSE([], status=401, body=b"bad key"))
    with p:
        try:
            await _drain(client)
        except LLMError as e:
            assert "API key" in str(e), e
        else:
            raise AssertionError("auth error harus jadi LLMError")

    # 4. Not-found → LLMError
    p, _ = _client_for(_FakeSSE([], status=404, body=b"nope"))
    with p:
        try:
            await _drain(client)
        except LLMError as e:
            assert "tidak ditemukan" in str(e), e
        else:
            raise AssertionError("not-found harus jadi LLMError")

    # 5. Koneksi putus 3x → retry lalu LLMError
    calls = {"n": 0}

    def _flaky(self: Any, *a: Any, **k: Any) -> Any:
        calls["n"] += 1
        raise _httpx.ConnectError("down")

    p, _ = _client_for(_FakeSSE([]))
    with p, _patch.object(_FakeClient, "stream", _flaky), _patch(
            "core.llm_client.asyncio.sleep", return_value=None):
        try:
            await _drain(client)
        except LLMError as e:
            assert "Gagal konek" in str(e), e
        else:
            raise AssertionError("conn error harus jadi LLMError")
    assert calls["n"] == MAX_CONNECTION_RETRIES + 1, calls

    # 6. Routing anthropic → endpoint messages + x-api-key
    cfg_a = Config(model="anthropic/claude-haiku-4-5", api_key="sk-ant")
    client_a = LLMClient(cfg_a)
    lines = ["event: content_block_delta",
             'data: {"delta": {"type": "text_delta", "text": "hai"}}',
             "event: message_stop", "data: {}"]
    p, fake = _client_for(_FakeSSE(lines))
    with p:
        async for ev in client_a.stream_completion(
                [{"role": "user", "content": "hi"}]):
            if isinstance(ev, _canon.StreamDone):
                assert ev.text == "hai", ev
    assert fake.seen["url"] == "https://api.anthropic.com/v1/messages"
    assert fake.seen["headers"]["x-api-key"] == "sk-ant"

    # 7. Model ngawur → LLMError jelas (tanpa network)
    cfg_bad = Config(model="ngawur/xyz", api_key="k")
    try:
        await _drain(LLMClient(cfg_bad))
    except LLMError as e:
        assert "tidak dikenali" in str(e), e
    else:
        raise AssertionError("model ngawur harus ditolak")

    print("✅ llm_client self-test OK (native adapter + retry)")


async def _live_test(prompt: str) -> None:
    cfg = load_config()
    client = setup_client(cfg)
    print(f"model: {cfg.model} — streaming...\n---")
    async for event in client.stream_completion([{"role": "user", "content": prompt}]):
        if isinstance(event, StreamText):
            print(event.content, end="", flush=True)
        elif isinstance(event, StreamDone):
            print(f"\n---\n✅ done. tool_calls={len(event.tool_calls)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", metavar="PROMPT", default=None,
                        help="test live ke provider (butuh config valid)")
    args = parser.parse_args()
    if args.live:
        asyncio.run(_live_test(args.live))
    else:
        asyncio.run(_self_test())
