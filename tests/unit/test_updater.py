"""Unit: updater — compare, cache, silent-fail (tanpa network asli)."""

from __future__ import annotations

from core import updater
from core.updater import check, is_newer


def test_compare_release_beats_prerelease():
    assert is_newer("1.0.0", "1.0.0-beta")
    assert not is_newer("1.0.0-beta", "1.0.0")
    assert not is_newer("1.0.0", "1.0.0")


def test_compare_numeric():
    assert is_newer("1.0.1", "1.0.0")
    assert is_newer("v1.1.0", "1.0.9")
    assert not is_newer("0.9.0", "1.0.0")


def test_compare_garbage_never_newer():
    assert not is_newer("ngawur", "1.0.0")
    assert not is_newer("1.0.0", "ngawur")


def test_newer_available(monkeypatch, isolated_home):
    monkeypatch.setattr(updater, "get_current_version", lambda: "0.1.0")
    r = check(fetch=lambda: "99.0.0")
    assert r["update_available"] and r["latest_version"] == "99.0.0"


def test_same_version_no_notice(monkeypatch, isolated_home):
    monkeypatch.setattr(updater, "get_current_version", lambda: "1.0.0")
    r = check(fetch=lambda: "1.0.0")
    assert not r["update_available"]


def test_offline_silent(monkeypatch, isolated_home):
    monkeypatch.setattr(updater, "get_current_version", lambda: "1.0.0")

    def _down():
        raise RuntimeError("offline")

    r = check(fetch=_down)
    assert r == {"update_available": False, "latest_version": None,
                 "current_version": "1.0.0"}


def test_fresh_cache_skips_network(monkeypatch, isolated_home):
    monkeypatch.setattr(updater, "get_current_version", lambda: "0.1.0")
    assert check(fetch=lambda: "99.0.0")["update_available"]

    def _boom():
        raise AssertionError("network kepanggil padahal cache segar")

    assert check(fetch=_boom)["latest_version"] == "99.0.0"


def test_update_parser_routing():
    from main import parse_args

    assert parse_args(["update"]).cmd == "update"
    assert parse_args([]).cmd is None  # default = TUI
