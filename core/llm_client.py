"""LLM client — wrapper LiteLLM: streaming + tool call + retry.

Dipakai oleh agent loop (Step 7) lewat async generator:

    client = setup_client(config)
    async for event in client.stream_completion(messages, tools):
        if isinstance(event, StreamText):
            ... tampilkan event.content ke TUI ...
        elif isinstance(event, StreamDone):
            ... event.text = teks penuh, event.tool_calls = [ToolCallRequest] ...

Test cepat tanpa API key (logika akumulasi + error mapping):
    python -m core.llm_client
Test live (butuh ~/.multacd/config.yaml yang valid):
    python -m core.llm_client --live "hello"
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import litellm
from litellm import (
    APIConnectionError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)

from core.config import Config, load_config

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
    """Stream selesai: teks penuh + daftar tool call (bisa kosong)."""

    text: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)


StreamEvent = StreamText | StreamDone


def setup_client(config: Config) -> LLMClient:
    """Init client dari config (LiteLLM stateless — ini bungkus kwargs + retry)."""
    return LLMClient(config)


class LLMClient:
    def __init__(self, config: Config) -> None:
        self.config = config

    def _base_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "api_key": self.config.api_key,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "timeout": REQUEST_TIMEOUT,
        }
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base
        return kwargs

    async def stream_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Kirim messages ke LLM, yield StreamText lalu diakhiri satu StreamDone.

        Retry hanya dilakukan jika stream BELUM menghasilkan teks apapun
        (aman — tidak ada duplikasi output). Gagal di tengah stream
        langsung raise LLMError.
        """
        kwargs = self._base_kwargs()
        if tools:
            kwargs["tools"] = tools

        conn_attempts = 0
        rate_attempts = 0
        while True:
            accumulator = _StreamAccumulator()
            yielded_any_text = False
            try:
                stream = await litellm.acompletion(stream=True, messages=messages, **kwargs)
                async for chunk in stream:
                    for event in accumulator.feed(chunk):
                        if isinstance(event, StreamText) and event.content:
                            yielded_any_text = True
                        yield event
                yield accumulator.done()
                return
            except RateLimitError as e:
                rate_attempts += 1
                if rate_attempts > MAX_RATE_LIMIT_RETRIES or yielded_any_text:
                    raise LLMError(
                        "⏳ Rate limit dari provider (429) — "
                        f"sudah retry {MAX_RATE_LIMIT_RETRIES}x, masih dibatasi. "
                        "Tunggu sebentar lalu coba lagi."
                    ) from e
                await asyncio.sleep(RETRY_BASE_DELAY * (2 ** (rate_attempts - 1)))
            except APIConnectionError as e:
                conn_attempts += 1
                if conn_attempts > MAX_CONNECTION_RETRIES or yielded_any_text:
                    raise LLMError(
                        "🌐 Gagal konek ke LLM provider "
                        f"({MAX_CONNECTION_RETRIES}x percobaan). "
                        "Cek koneksi internet / api_base di config."
                    ) from e
                await asyncio.sleep(RETRY_BASE_DELAY * conn_attempts)
            except AuthenticationError as e:
                raise LLMError(
                    "🔑 API key ditolak provider. Cek `api_key` di ~/.multacd/config.yaml "
                    "(BYOK — pastikan key cocok dengan `model` yang dipilih)."
                ) from e
            except NotFoundError as e:
                raise LLMError(
                    f"🔍 Model `{self.config.model}` tidak ditemukan oleh provider. "
                    "Cek penulisan `model` di config (format LiteLLM, mis. "
                    "`anthropic/claude-sonnet-4-6`, `openai/gpt-4o`)."
                ) from e
            except LLMError:
                raise
            except Exception as e:
                raise LLMError(f"❌ LLM error tak terduga ({type(e).__name__}): {e}") from e

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


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Ambil atribut ATAU key dict — chunk LiteLLM bisa berbentuk keduanya."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class _StreamAccumulator:
    """Rakit fragment streaming LiteLLM jadi teks + tool call utuh."""

    def __init__(self) -> None:
        self._text_parts: list[str] = []
        self._calls: dict[int, dict[str, Any]] = {}

    def feed(self, chunk: Any) -> list[StreamText]:
        events: list[StreamText] = []
        choices = _get(chunk, "choices", []) or []
        if not choices:
            return events
        delta = _get(choices[0], "delta", {}) or {}

        content = _get(delta, "content")
        if content:
            self._text_parts.append(content)
            events.append(StreamText(content))

        for tc in _get(delta, "tool_calls", None) or []:
            index = _get(tc, "index", 0) or 0
            slot = self._calls.setdefault(index, {"id": "", "name": "", "args": ""})
            tc_id = _get(tc, "id")
            if tc_id:
                slot["id"] = tc_id
            func = _get(tc, "function", {}) or {}
            name = _get(func, "name")
            if name:
                slot["name"] = name
            args = _get(func, "arguments")
            if args:
                slot["args"] += args
        return events

    def done(self) -> StreamDone:
        calls: list[ToolCallRequest] = []
        for index in sorted(self._calls):
            slot = self._calls[index]
            name = slot["name"]
            if not name:
                continue  # fragment tanpa nama — abaikan
            raw_args = slot["args"] or "{}"
            try:
                arguments = json.loads(raw_args)
            except json.JSONDecodeError as e:
                raise LLMError(
                    f"❌ LLM mengirim tool_call `{name}` dengan argumen bukan JSON valid: {e}"
                ) from e
            if not isinstance(arguments, dict):
                raise LLMError(
                    f"❌ Argumen tool_call `{name}` harus object JSON, dapat: {type(arguments).__name__}"
                )
            calls.append(ToolCallRequest(id=slot["id"] or f"call_{index}", name=name, arguments=arguments))
        return StreamDone(text="".join(self._text_parts), tool_calls=calls)


# ── Self-test (tanpa API key) ──────────────────────────────────────────────

def _fake_chunk(text: str = "", tool_deltas: list[dict] | None = None) -> dict:
    return {
        "choices": [
            {"delta": {"content": text, "tool_calls": tool_deltas or []}},
        ]
    }


async def _self_test() -> None:
    # 1. Teks murni
    acc = _StreamAccumulator()
    events: list[StreamEvent] = []
    for ch in [_fake_chunk("Halo, "), _fake_chunk("dunia!")]:
        events += acc.feed(ch)
    done = acc.done()
    assert [e.content for e in events] == ["Halo, ", "dunia!"], events
    assert done.text == "Halo, dunia!" and done.tool_calls == []

    # 2. Tool call terpecah jadi fragment (kasus nyata streaming)
    acc = _StreamAccumulator()
    acc.feed(_fake_chunk("bentar, ", [{"index": 0, "id": "call_1",
            "function": {"name": "read_file", "arguments": '{"path": "ma'}}]))
    acc.feed(_fake_chunk("", [{"index": 0, "function": {"arguments": 'in.py"}'}}]))
    acc.feed(_fake_chunk("", [{"index": 1, "id": "call_2",
            "function": {"name": "bash", "arguments": '{"command": "ls"}'}}]))
    done = acc.done()
    assert done.text == "bentar, ", done.text
    assert len(done.tool_calls) == 2, done.tool_calls
    assert done.tool_calls[0].name == "read_file"
    assert done.tool_calls[0].arguments == {"path": "main.py"}, done.tool_calls[0].arguments
    assert done.tool_calls[1].name == "bash"

    # 3. Argumen bukan JSON → LLMError (bukan crash)
    acc = _StreamAccumulator()
    acc.feed(_fake_chunk("", [{"index": 0, "function": {"name": "x", "arguments": "{oops"}}]))
    try:
        acc.done()
    except LLMError:
        pass
    else:
        raise AssertionError("argumen invalid harus raise LLMError")

    # 4. Error mapping: auth, not-found, retry koneksi 3x
    from unittest.mock import patch

    cfg = Config(model="openai/gpt-4o", api_key="sk-bad")
    client = LLMClient(cfg)

    async def _drain(c: LLMClient) -> StreamDone:
        async for ev in c.stream_completion([{"role": "user", "content": "hi"}]):
            if isinstance(ev, StreamDone):
                return ev
        raise AssertionError("unreachable")

    with patch("core.llm_client.litellm.acompletion", side_effect=AuthenticationError("bad", "x", "x")):
        try:
            await _drain(client)
        except LLMError as e:
            assert "API key" in str(e), e
        else:
            raise AssertionError("auth error harus jadi LLMError")

    with patch("core.llm_client.litellm.acompletion", side_effect=NotFoundError("nf", "x", "x")):
        try:
            await _drain(client)
        except LLMError as e:
            assert "tidak ditemukan" in str(e), e
        else:
            raise AssertionError("not-found harus jadi LLMError")

    calls = {"n": 0}

    async def _flaky(*a: Any, **k: Any) -> Any:
        calls["n"] += 1
        raise APIConnectionError("down", "x", "x")

    with patch("core.llm_client.litellm.acompletion", side_effect=_flaky):
        with patch("core.llm_client.asyncio.sleep", return_value=None):
            try:
                await _drain(client)
            except LLMError as e:
                assert "Gagal konek" in str(e), e
            else:
                raise AssertionError("conn error harus jadi LLMError")
    assert calls["n"] == MAX_CONNECTION_RETRIES + 1, calls

    print("✅ llm_client self-test OK (akumulasi + error mapping + retry)")


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
