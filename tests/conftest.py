"""Shared fixtures Phase 5 Step 1 — isolasi + mock, tanpa API nyata."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from core.config import Config


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """MULTACD_HOME menunjuk tmp — tidak sentuh data asli user."""
    monkeypatch.setenv("MULTACD_HOME", str(tmp_path))
    monkeypatch.setenv("MULTACD_CONFIG", str(tmp_path / ".multacd" / "config.yaml"))
    return tmp_path


@pytest.fixture()
def sample_config() -> Config:
    """Config valid minimal buat unit/integration test."""
    return Config(model="m", api_key="k")


@pytest.fixture()
def config_file(tmp_path: Path) -> Path:
    """config.yaml valid di tmp — buat test load_config."""
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({"model": "m", "api_key": "k"}), encoding="utf-8")
    return p


class FakeLLM:
    """LLM scripted — antrean StreamDone, tanpa network."""

    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.seen: list = []

    async def stream_completion(self, messages, tools=None):
        from core.llm_client import StreamDone, StreamText

        self.seen.append(messages)
        done = self.script.pop(0)
        assert isinstance(done, StreamDone)
        for word in done.text.split():
            yield StreamText(word + " ")
        yield done


@pytest.fixture()
def fake_llm_factory():
    """Factory FakeLLM(script) — tiap test bikin script sendiri."""
    return FakeLLM


@pytest.fixture()
def workdir(tmp_path: Path) -> Path:
    """Folder kerja kosong buat test tool filesystem."""
    d = tmp_path / "work"
    d.mkdir()
    return d


# Biarkan MULTACD_HOME bawaan test_selftests (isolated) tetap berlaku
# kalau ada test yang lupa pakai fixture — jangan baca home asli.
os.environ.setdefault("MULTACD_HOME", os.environ.get("MULTACD_HOME", "/tmp"))
