"""Unit: kredensial per-provider (#31) — validasi, persist, routing LLM.

Tanpa network (httpx dimock), tanpa config asli (isolated_home).
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
import yaml

from core.config import (
    Config,
    ConfigError,
    load_config,
    resolve_config_path,
    save_config_updates,
)
from core.providers import provider_id_of


def test_provider_id_of():
    assert provider_id_of("openai/gpt-4o") == "openai"
    assert provider_id_of("Anthropic/claude-x") == "anthropic"
    assert provider_id_of("gpt-4o") == ""
    assert provider_id_of("") == ""
    assert provider_id_of("zai-org/GLM-5.3-Flash") == "zai-org"


def test_strmap_validation():
    cfg = Config(model="m", api_key="k",
                 provider_keys={"OpenAI": "sk-x", "kosong": "  "},
                 provider_bases={"custom": "http://x/v1"})
    assert cfg.provider_keys == {"openai": "sk-x"}  # lower + prune kosong
    assert cfg.provider_bases == {"custom": "http://x/v1"}
    with pytest.raises(ConfigError):
        Config(model="m", api_key="k", provider_keys={"openai": 123})
    with pytest.raises(ConfigError):
        Config(model="m", api_key="k", provider_keys=["bukan-dict"])
    cfg = Config(model="m", api_key="k", provider_keys=None)
    assert cfg.provider_keys == {}


def test_save_merges_and_prunes(isolated_home):
    path = resolve_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"model": "m", "api_key": "k",
                                    "provider_keys": {"a": "1"}}),
                    encoding="utf-8")
    save_config_updates({"model": "openai/gpt-4o",
                         "provider_keys": {"openai": "sk-x"}})
    cfg = load_config()
    assert cfg.model == "openai/gpt-4o" and cfg.api_key == "k"
    assert cfg.provider_keys == {"a": "1", "openai": "sk-x"}
    # "" = hapus key (buat `/base -`).
    save_config_updates({"provider_keys": {"a": ""}})
    assert load_config().provider_keys == {"openai": "sk-x"}


def _sse_done(text="hi"):
    import json as _json
    return [f"data: {_json.dumps({'choices': [{'delta': {'content': text}}]})}",
            "data: [DONE]"]


class _Resp:
    status_code = 200

    def __init__(self, lines):
        self._lines = lines

    async def aiter_lines(self):
        for ln in self._lines:
            yield ln

    async def aread(self):
        return b""


class _Ctx:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *a):
        return None


class _Client:
    def __init__(self, resp):
        self._resp = resp
        self.seen: dict = {}

    def stream(self, method, url, **kw):
        self.seen = {"url": url, **kw}
        return _Ctx(self._resp)

    async def aclose(self):
        pass


def _run_llm(cfg):
    import core.llm_client as _canon

    async def _drain():
        client = _canon.LLMClient(cfg)
        async for ev in client.stream_completion(
                [{"role": "user", "content": "hi"}]):
            if isinstance(ev, _canon.StreamDone):
                return ev
        raise AssertionError("unreachable")

    fake = _Client(_Resp(_sse_done()))
    with patch("httpx.AsyncClient", return_value=fake):
        asyncio.run(_drain())
    return fake.seen


def test_llm_uses_provider_key():
    cfg = Config(model="anthropic/claude-haiku-4-5", api_key="sk-lama",
                 provider_keys={"anthropic": "sk-ant-baru"})
    seen = _run_llm(cfg)
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == "sk-ant-baru"


def test_llm_falls_back_to_top_level():
    cfg = Config(model="groq/llama-3.3-70b-versatile", api_key="gsk-x")
    seen = _run_llm(cfg)
    assert "groq" in seen["url"]
    assert seen["headers"]["Authorization"] == "Bearer gsk-x"


def test_llm_uses_provider_base():
    cfg = Config(model="zai-org/GLM-5.3-Flash", api_key="k",
                 provider_bases={"zai-org": "https://api.z.ai/v1"})
    seen = _run_llm(cfg)
    assert seen["url"] == "https://api.z.ai/v1/chat/completions"
