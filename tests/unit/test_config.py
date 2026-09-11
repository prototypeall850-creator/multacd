"""Unit: config valid / hilang / field wajib / override path."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.config import load_config, resolve_config_path


def test_load_valid(config_file: Path):
    cfg = load_config(config_file)
    assert cfg.model == "m" and cfg.api_key == "k"


def test_missing_config_raises(tmp_path: Path):
    missing = tmp_path / "tidak-ada.yaml"
    with pytest.raises(SystemExit):
        load_config(missing)


def test_empty_config_raises(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit):
        load_config(p)


def test_blank_model_rejected(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({"model": "  ", "api_key": "k"}), encoding="utf-8")
    with pytest.raises(SystemExit):
        load_config(p)


def test_blank_api_key_rejected(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({"model": "m", "api_key": " "}), encoding="utf-8")
    with pytest.raises(SystemExit):
        load_config(p)


def test_explicit_path_beats_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_cfg = tmp_path / "env.yaml"
    monkeypatch.setenv("MULTACD_CONFIG", str(env_cfg))
    explicit = tmp_path / "explicit.yaml"
    assert resolve_config_path(explicit) == explicit
    assert resolve_config_path(None) == env_cfg


def test_provider_normalized_case_insensitive():
    from core.config import Config

    cfg = Config(model="m", api_key="k", search_provider=" Tavily ")
    assert cfg.search_provider == "tavily"
