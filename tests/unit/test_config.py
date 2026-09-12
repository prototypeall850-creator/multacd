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


def test_empty_optional_keys_forgiven(tmp_path: Path):
    """YAML `key:` kosong → None. Blok opsional dimaafkan (bot nonaktif),
    bukan error 'dapat NoneType'. Field wajib tetap ditolak ramah."""
    from core.config import Config, ConfigError

    # telegram kosong semua = bot nonaktif, lolos
    c = Config(model="m", api_key="k", telegram={
        "bot_token": None, "admin_id": None,
        "admin_username": None, "allowed_users": None})
    assert c.telegram.bot_token == "" and c.telegram.admin_id == 0
    assert c.telegram.admin_username == "" and c.telegram.allowed_users == []
    # `telegram:` tanpa isi + `schedules:` kosong
    assert Config(model="m", api_key="k", telegram=None).telegram.bot_token == ""
    assert Config(model="m", api_key="k", schedules=None).schedules == []
    # file gaya user: admin_id di-comment → lolos, admin_id 0
    p = tmp_path / "config.yaml"
    p.write_text("model: m\napi_key: k\ntelegram:\n"
                 "  bot_token: 123:abc\n  admin_username: dari\n",
                 encoding="utf-8")
    cfg = load_config(p)
    assert cfg.telegram.admin_id == 0
    assert cfg.telegram.admin_username == "dari"
    # field wajib kosong tetap ditolak, pesan ramah (bukan NoneType)
    with pytest.raises(ConfigError) as exc:
        Config(model=None, api_key="k")
    assert "model: wajib diisi (kosong)" in str(exc.value)
    # angka wajib kosong tetap ditolak via gt
    with pytest.raises(ConfigError):
        Config(model="m", api_key="k", max_tokens=None)
