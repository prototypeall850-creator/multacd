"""Adapter Anthropic Messages API — format beda, kontrak sama.

Pembedanya dari OpenAI: system terpisah, tool_use/tool_result blocks,
SSE berbasis event (message_start/delta, content_block_*).
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


def convert_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """History OpenAI-ish → (system, messages Anthropic). Pure function.

    - system digabung (Anthropic: param terpisah, bukan role).
    - assistant + tool_calls (format OpenAI) → content blocks text/tool_use.
    - tool → user + tool_result blocks.
    """
    systems: list[str] = []
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role", "user")
        if role == "system":
            content = m.get("content")
            if content:
                systems.append(str(content))
            continue
        if role == "tool":
            out.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id", ""),
                    "content": str(m.get("content", "")),
                }],
            })
            continue
        if role == "assistant" and m.get("tool_calls"):
            blocks: list[dict[str, Any]] = []
            if m.get("content"):
                blocks.append({"type": "text", "text": str(m["content"])})
            for tc in m["tool_calls"]:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                args = fn.get("arguments", "{}") if isinstance(fn, dict) else "{}"
                try:
                    parsed = json.loads(args) if isinstance(args, str) else args
                except json.JSONDecodeError:
                    parsed = {}
                blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", "") if isinstance(tc, dict) else "",
                    "name": fn.get("name", "") if isinstance(fn, dict) else "",
                    "input": parsed if isinstance(parsed, dict) else {},
                })
            out.append({"role": "assistant", "content": blocks})
            continue
        out.append({"role": "assistant" if role == "assistant" else "user",
                    "content": str(m.get("content", ""))})
    return ("\n\n".join(systems), out)


def convert_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Definisi OpenAI function → Anthropic tools. Pure function."""
    out = []
    for t in tools or []:
        fn = t.get("function", {}) if isinstance(t, dict) else {}
        out.append({
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object"}),
        })
    return [t for t in out if t["name"]]


class AnthropicAccumulator:
    """Rakit SSE Anthropic jadi teks + tool call + usage."""

    def __init__(self) -> None:
        self._text_parts: list[str] = []
        self._blocks: dict[int, dict[str, Any]] = {}  # index → tool_use
        self._prompt_tokens = 0
        self._completion_tokens = 0

    def feed_event(self, event: str, data: dict[str, Any]) -> list[StreamText]:
        """Satu SSE (event + data). Return teks baru."""
        events: list[StreamText] = []
        if event == "message_start":
            usage = data.get("message", {}).get("usage", {})
            self._prompt_tokens = usage.get("input_tokens", 0) or 0
        elif event == "content_block_start":
            block = data.get("content_block", {})
            if block.get("type") == "tool_use":
                self._blocks[data.get("index", 0)] = {
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "json": "",
                }
        elif event == "content_block_delta":
            delta = data.get("delta", {})
            dtype = delta.get("type")
            if dtype == "text_delta" and delta.get("text"):
                self._text_parts.append(delta["text"])
                events.append(StreamText(delta["text"]))
            elif dtype == "input_json_delta" and delta.get("partial_json"):
                slot = self._blocks.get(data.get("index", 0))
                if slot is not None:
                    slot["json"] += delta["partial_json"]
        elif event == "message_delta":
            usage = data.get("usage", {})
            self._completion_tokens = usage.get("output_tokens", 0) or 0
        return events

    def done(self, model: str) -> StreamDone:
        calls = []
        for index in sorted(self._blocks):
            b = self._blocks[index]
            if not b["name"]:
                continue
            try:
                arguments = json.loads(b["json"] or "{}")
            except json.JSONDecodeError as e:
                raise ProviderError(
                    f"LLM mengirim tool_call `{b['name']}` dengan argumen "
                    f"bukan JSON valid: {e}")
            if not isinstance(arguments, dict):
                raise ProviderError(
                    f"Argumen tool_call `{b['name']}` harus object JSON.")
            calls.append(ToolCallRequest(id=b["id"] or f"call_{index}",
                                         name=b["name"], arguments=arguments))
        return StreamDone(
            text="".join(self._text_parts), tool_calls=calls,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            cost_usd=estimate_cost(model, self._prompt_tokens,
                                   self._completion_tokens))


def map_http_error(status: int, body: str, model: str) -> ProviderError:
    snippet = (body or "")[:300]
    if status in (401, 403):
        return ProviderAuthError(
            f"API key ditolak provider ({status}). {snippet}".strip())
    if status == 404:
        return ProviderNotFoundError(
            f"Model `{model}` tidak ditemukan oleh provider. {snippet}".strip())
    if status in (429, 529):
        return ProviderRateLimitError(
            f"Rate limit/overload dari provider ({status}). {snippet}".strip())
    return ProviderError(f"Provider error HTTP {status}. {snippet}".strip())


async def stream_chat(spec: ProviderSpec, api_key: str,
                      messages: list[dict[str, Any]],
                      tools: list[dict[str, Any]] | None,
                      max_tokens: int, temperature: float,
                      timeout: float,
                      client: httpx.AsyncClient | None = None,
                      ) -> AsyncIterator[StreamText | StreamDone]:
    """Kirim Messages API streaming. `client` injeksi buat test."""
    system, convo = convert_messages(messages)
    body: dict[str, Any] = {
        "model": spec.model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": convo,
        "stream": True,
    }
    if system:
        body["system"] = system
    converted = convert_tools(tools)
    if converted:
        body["tools"] = converted
    headers = {"Content-Type": "application/json", "x-api-key": api_key,
               **spec.headers}
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
                    err_text = (await resp.aread()).decode("utf-8", "replace")
                except Exception:
                    err_text = ""
                raise map_http_error(resp.status_code, err_text, spec.model)
            acc = AnthropicAccumulator()
            cur_event = "message"
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("event:"):
                    cur_event = line[len("event:"):].strip()
                    continue
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict):
                    for ev in acc.feed_event(cur_event, data):
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

    # 1. Konversi pesan: system dipisah, tool chain jadi blocks
    sys, convo = convert_messages([
        {"role": "system", "content": "kamu A"},
        {"role": "system", "content": "aturan B"},
        {"role": "user", "content": "baca x"},
        {"role": "assistant", "content": "ok",
         "tool_calls": [{"id": "c1", "type": "function",
                         "function": {"name": "read_file",
                                      "arguments": '{"path": "x"}'}}]},
        {"role": "tool", "tool_call_id": "c1", "name": "read_file",
         "content": "isi"},
    ])
    assert sys == "kamu A\n\naturan B", sys
    assert convo[0] == {"role": "user", "content": "baca x"}
    assert convo[1]["content"][0] == {"type": "text", "text": "ok"}
    assert convo[1]["content"][1]["type"] == "tool_use"
    assert convo[1]["content"][1]["input"] == {"path": "x"}
    assert convo[2]["content"][0]["type"] == "tool_result"

    # 2. Konversi tools
    assert convert_tools(None) == []
    at = convert_tools([{"function": {"name": "bash", "description": "sh",
                                      "parameters": {"type": "object"}}}])
    assert at == [{"name": "bash", "description": "sh",
                   "input_schema": {"type": "object"}}], at

    # 3. Akumulasi SSE Anthropic
    acc = AnthropicAccumulator()
    acc.feed_event("message_start", {"message": {"usage": {"input_tokens": 50}}})
    acc.feed_event("content_block_start", {"index": 0, "content_block": {
        "type": "tool_use", "id": "t1", "name": "bash"}})
    acc.feed_event("content_block_delta", {"index": 0, "delta": {
        "type": "text_delta", "text": "jalan "}})
    acc.feed_event("content_block_delta", {"index": 0, "delta": {
        "type": "input_json_delta", "partial_json": '{"command": "ls"}'}})
    acc.feed_event("message_delta", {"usage": {"output_tokens": 12}})
    done = acc.done("claude-sonnet-4-6")
    assert done.text == "jalan " and len(done.tool_calls) == 1
    assert done.tool_calls[0].arguments == {"command": "ls"}
    assert (done.prompt_tokens, done.completion_tokens) == (50, 12)
    assert done.cost_usd > 0

    # 4. Stream penuh via mock
    class _FakeResp:
        status_code = 200

        async def aiter_lines(self):
            yield "event: content_block_delta"
            yield 'data: {"delta": {"type": "text_delta", "text": "hai"}}'
            yield "event: message_delta"
            yield 'data: {"usage": {"output_tokens": 3}}'
            yield "event: message_stop"
            yield "data: {}"

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
        spec = _PS(kind="anthropic", chat_url="http://x", api_key="",
                   model="claude-haiku-4-5", headers={})
        out = [e async for e in stream_chat(
            spec, "k", [{"role": "user", "content": "hi"}], None,
            10, 0.0, 5.0, client=_FakeClient())]
        assert isinstance(out[-1], StreamDone) and out[-1].text == "hai", out
        sent = _FakeClient.seen[1]["json"]
        assert sent["model"] == "claude-haiku-4-5" and sent["stream"] is True
        assert _FakeClient.seen[1]["headers"]["x-api-key"] == "k"

    _asyncio.run(_run())
    print("✅ anthropic self-test OK (konversi + SSE + mock)")
