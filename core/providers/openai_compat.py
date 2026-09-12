"""Adapter OpenAI-compatible — 1 jalur buat OpenAI/Groq/DeepSeek/Gemini/Ollama/custom.

Chat Completions + SSE + function calling + usage. Format yang dipakai
LLM modern; beda provider cuma beda base URL & key (lihat resolve_provider).
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.llm_client import StreamDone, StreamText, ToolCallRequest
from core.providers import (
    ProviderAuthError,
    ProviderConnectionError,
    ProviderError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderSpec,
    estimate_cost,
)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def parse_sse_line(line: str) -> dict[str, Any] | None:
    """Satu baris SSE → dict, '[DONE]' → {} (selesai), lain → None.

    Pure function —SSE aneh (komentar ':', baris kosong) diabaikan.
    """
    line = line.strip()
    if not line or line.startswith(":"):
        return None
    if not line.startswith("data:"):
        return None
    payload = line[len("data:"):].strip()
    if payload == "[DONE]":
        return {}
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


class OpenAIStreamAccumulator:
    """Rakit fragment SSE jadi teks + tool call + usage."""

    def __init__(self) -> None:
        self._text_parts: list[str] = []
        self._calls: dict[int, dict[str, Any]] = {}
        self._prompt_tokens = 0
        self._completion_tokens = 0

    def feed_chunk(self, data: dict[str, Any]) -> list[StreamText]:
        """Satu dict SSE ({} = [DONE], abaikan). Return teks baru."""
        events: list[StreamText] = []
        if not data:
            return events
        usage = data.get("usage")
        if isinstance(usage, dict):
            self._prompt_tokens = usage.get("prompt_tokens", 0) or 0
            self._completion_tokens = usage.get("completion_tokens", 0) or 0
        choices = data.get("choices") or []
        if not choices or not isinstance(choices, list):
            return events
        delta = _get(choices[0], "delta", {}) or {}
        content = _get(delta, "content")
        if content:
            self._text_parts.append(content)
            events.append(StreamText(content))
        for tc in _get(delta, "tool_calls", None) or []:
            index = _get(tc, "index", 0) or 0
            slot = self._calls.setdefault(
                index, {"id": "", "name": "", "args": ""})
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

    def done(self, model: str) -> StreamDone:
        calls: list[ToolCallRequest] = []
        for index in sorted(self._calls):
            slot = self._calls[index]
            if not slot["name"]:
                continue
            try:
                arguments = json.loads(slot["args"] or "{}")
            except json.JSONDecodeError as e:
                raise ProviderError(
                    f"LLM mengirim tool_call `{slot['name']}` dengan argumen "
                    f"bukan JSON valid: {e}")
            if not isinstance(arguments, dict):
                raise ProviderError(
                    f"Argumen tool_call `{slot['name']}` harus object JSON.")
            calls.append(ToolCallRequest(
                id=slot["id"] or f"call_{index}", name=slot["name"],
                arguments=arguments))
        return StreamDone(
            text="".join(self._text_parts), tool_calls=calls,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            cost_usd=estimate_cost(model, self._prompt_tokens,
                                   self._completion_tokens))


def map_http_error(status: int, body: str, model: str) -> ProviderError:
    """Status HTTP → error typed (401/404/429 dipisah buat retry)."""
    snippet = (body or "")[:300]
    if status in (401, 403):
        return ProviderAuthError(
            f"API key ditolak provider ({status}). {snippet}".strip())
    if status == 404:
        return ProviderNotFoundError(
            f"Model `{model}` tidak ditemukan oleh provider. {snippet}".strip())
    if status == 429:
        return ProviderRateLimitError(
            f"Rate limit dari provider (429). {snippet}".strip())
    return ProviderError(f"Provider error HTTP {status}. {snippet}".strip())


def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bersihkan messages sebelum kirim (ala opencode transform.ts).

    - `tool_calls: []` / None → key di-drop (provider strict 400 kalau
      array kosong ikut terkirim — issue #25).
    - `content: None` tanpa tool_calls → `""` (beberapa gateway nolak null).
    - `content: None` + tool_calls non-kosong → dibiarkan (valid OpenAI).
    Pure function — input tidak dimutasi.
    """
    clean: list[dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        msg = dict(m)
        tcs = msg.get("tool_calls")
        if not tcs:
            msg.pop("tool_calls", None)
        if msg.get("content") is None and not msg.get("tool_calls"):
            msg["content"] = ""
        clean.append(msg)
    return clean


async def stream_chat(spec: ProviderSpec, api_key: str,
                      messages: list[dict[str, Any]],
                      tools: list[dict[str, Any]] | None,
                      max_tokens: int, temperature: float,
                      timeout: float,
                      client: httpx.AsyncClient | None = None,
                      ) -> AsyncIterator[StreamText | StreamDone]:
    """Kirim chat completions streaming. `client` injeksi buat test."""
    body: dict[str, Any] = {
        "model": spec.model,
        "messages": _sanitize_messages(messages),
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        body["tools"] = tools
    headers = {"Content-Type": "application/json", **spec.headers}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=timeout)
    assert client is not None
    try:
        try:
            resp_ctx = client.stream("POST", spec.chat_url, json=body,
                                     headers=headers)
            resp = await resp_ctx.__aenter__()
        except httpx.TimeoutException as e:
            raise ProviderConnectionError(f"Koneksi timeout: {e}")
        except httpx.HTTPError as e:
            raise ProviderConnectionError(f"Gagal konek: {e}")
        try:
            if resp.status_code != 200:
                try:
                    err_body = await resp.aread()
                    err_text = err_body.decode("utf-8", "replace")
                except Exception:
                    err_text = ""
                raise map_http_error(resp.status_code, err_text, spec.model)
            acc = OpenAIStreamAccumulator()
            async for line in resp.aiter_lines():
                data = parse_sse_line(line)
                if data is None:
                    continue
                for ev in acc.feed_chunk(data):
                    if ev.content:
                        yield ev
            yield acc.done(spec.model)
        finally:
            with contextlib.suppress(Exception):
                await resp_ctx.__aexit__(None, None, None)
    finally:
        if own_client:
            with contextlib.suppress(Exception):
                await client.aclose()


if __name__ == "__main__":
    import asyncio as _asyncio

    # 1. Parse SSE: teks, komentar, [DONE], sampah
    assert parse_sse_line("") is None
    assert parse_sse_line(": ping") is None
    assert parse_sse_line("data: [DONE]") == {}
    assert parse_sse_line('data: {"a":1}') == {"a": 1}
    assert parse_sse_line("data: {oops") is None
    assert parse_sse_line("event: x") is None

    # 2. Akumulasi teks + tool terpecah + usage
    acc = OpenAIStreamAccumulator()
    evs = acc.feed_chunk({"choices": [{"delta": {"content": "halo "}}]})
    assert [e.content for e in evs] == ["halo "]
    acc.feed_chunk({"choices": [{"delta": {"tool_calls": [
        {"index": 0, "id": "c1",
         "function": {"name": "read_file", "arguments": '{"path": "ma'}}]}}]})
    acc.feed_chunk({"choices": [{"delta": {"tool_calls": [
        {"index": 0, "function": {"arguments": 'in.py"}'}}]}}]})
    acc.feed_chunk({"usage": {"prompt_tokens": 100, "completion_tokens": 20}})
    done = acc.done("gpt-4o")
    assert done.text == "halo " and len(done.tool_calls) == 1
    assert done.tool_calls[0].arguments == {"path": "main.py"}
    assert (done.prompt_tokens, done.completion_tokens) == (100, 20)
    assert done.cost_usd > 0  # gpt-4o ada harga

    # 3. Error mapping
    assert isinstance(map_http_error(401, "bad", "m"), ProviderAuthError)
    assert isinstance(map_http_error(404, "x", "m"), ProviderNotFoundError)
    assert isinstance(map_http_error(429, "x", "m"), ProviderRateLimitError)
    assert isinstance(map_http_error(500, "boom", "m"), ProviderError)

    # 4. Stream penuh via httpx mock (tanpa network)
    class _FakeResp:
        status_code = 200

        async def aiter_lines(self):
            yield 'data: {"choices": [{"delta": {"content": "hi"}}]}'
            yield 'data: {"usage": {"prompt_tokens": 10, "completion_tokens": 5}}'
            yield "data: [DONE]"

        async def aread(self):
            return b""

    class _FakeCtx:
        async def __aenter__(self):
            return _FakeResp()

        async def __aexit__(self, *a):
            return None

    class _FakeClient:
        def stream(self, *a, **k):
            _FakeClient.seen = (a, k)
            return _FakeCtx()

        async def aclose(self):
            pass

    async def _run() -> None:
        from core.providers import ProviderSpec as _PS
        spec = _PS(kind="openai", chat_url="http://x", api_key="",
                   model="gpt-4o-mini", headers={})
        out = [e async for e in stream_chat(
            spec, "k", [{"role": "user", "content": "hi"}], None,
            10, 0.0, 5.0, client=_FakeClient())]
        assert isinstance(out[-1], StreamDone) and out[-1].text == "hi", out
        assert (out[-1].prompt_tokens, out[-1].completion_tokens) == (10, 5)
        sent = _FakeClient.seen[1]["json"]
        assert sent["stream"] is True and sent["model"] == "gpt-4o-mini"

    _asyncio.run(_run())

    # 5. HTTP 401 → ProviderAuthError (tanpa network)
    class _BadResp(_FakeResp):
        status_code = 401

        async def aiter_lines(self):  # tak dipakai
            yield ""

    class _BadCtx(_FakeCtx):
        async def __aenter__(self):
            return _BadResp()

    class _BadClient(_FakeClient):
        def stream(self, *a, **k):
            return _BadCtx()

    async def _run_bad() -> None:
        from core.providers import ProviderSpec as _PS
        spec = _PS(kind="openai", chat_url="http://x", api_key="",
                   model="m", headers={})
        try:
            async for _ in stream_chat(spec, "k", [], None, 10, 0.0, 5.0,
                                       client=_BadClient()):
                pass
        except ProviderAuthError:
            return
        raise AssertionError("401 harus jadi auth error")

    _asyncio.run(_run_bad())
    print("✅ openai_compat self-test OK (parse + akumulasi + mock)")
