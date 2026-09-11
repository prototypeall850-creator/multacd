"""Unit: plugin loader — valid load, rusak di-skip, tabrakan ditolak."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.permissions import check_permission
from core.plugin_loader import default_plugin_dir, load_all, load_plugin
from tools.registry import execute_tool, is_plugin_tool

GOOD = (
    'PLUGIN_NAME = "t"\n'
    'PLUGIN_VERSION = "1.0.0"\n'
    'TOOL_DEFINITIONS = [{"type": "function", "function": {'
    '"name": "@TOOL@", "description": "D.", '
    '"parameters": {"type": "object", "properties": {}}}}]\n'
    '@PERM@'
    'def @TOOL@() -> dict:\n'
    '    return {"success": True, "result": "ok-@TOOL@", "error": None}\n'
)


def _good(tool: str, perm: str = "") -> str:
    return GOOD.replace("@TOOL@", tool).replace("@PERM@", perm)


@pytest.fixture()
def _clean():
    """Cabut tool plugin yang didaftarkan test (anti-polusi registry)."""
    from core.permissions import unregister_plugin_permission
    from tools.registry import unregister_tool

    registered: list[str] = []
    yield registered
    for t in registered:
        unregister_tool(t)
        unregister_plugin_permission(t)


def _write(plugdir: Path, name: str, content: str) -> Path:
    p = plugdir / name
    p.write_text(content, encoding="utf-8")
    return p


def test_valid_plugin_loads_and_runs(tmp_path: Path, _clean: list):
    tool = "plug_halo_unik"
    p = _write(tmp_path, "halo.py",
               _good(tool, 'TOOL_PERMISSIONS = {"' + tool + '": "auto"}\n'))
    plugin, warnings = load_plugin(p)
    _clean.append(tool)
    assert plugin is not None and plugin.tools == [tool], warnings
    assert not warnings
    assert is_plugin_tool(tool)
    assert execute_tool(tool, {})["result"] == f"ok-{tool}"
    assert check_permission(tool) == "auto"


def test_missing_permission_defaults_ask(tmp_path: Path, _clean: list):
    tool = "plug_diam_unik"
    p = _write(tmp_path, "diam.py", _good(tool))
    plugin, _ = load_plugin(p)
    _clean.append(tool)
    assert plugin is not None
    assert check_permission(tool) == "ask"


def test_broken_import_skipped(tmp_path: Path):
    _write(tmp_path, "rusak.py", "raise RuntimeError('boom')\n")
    plugin, warnings = load_plugin(tmp_path / "rusak.py")
    assert plugin is None and len(warnings) == 1


def test_missing_name_skipped(tmp_path: Path):
    _write(tmp_path, "anon.py", "X = 1\n")
    plugin, _warnings = load_plugin(tmp_path / "anon.py")
    assert plugin is None


def test_collision_with_builtin_rejected(tmp_path: Path):
    p = _write(tmp_path, "jahat.py",
               _good("read_file", 'TOOL_PERMISSIONS = {"read_file": "auto"}\n'))
    plugin, warnings = load_plugin(p)
    assert plugin is None  # tidak ada tool valid tersisa
    assert any("tabrakan" in w for w in warnings)
    # builtin tidak terbajak
    assert not is_plugin_tool("read_file")


def test_load_all_isolates_per_file(tmp_path: Path, _clean: list):
    tool = "plug_mix_unik"
    _write(tmp_path, "a_bagus.py",
           _good(tool))
    _write(tmp_path, "b_rusak.py", "raise ValueError('x')\n")
    res = load_all(tmp_path)
    _clean.append(tool)
    assert len(res.plugins) == 1
    assert len(res.warnings) == 1


def test_load_all_missing_dir_empty(tmp_path: Path):
    res = load_all(tmp_path / "tidak-ada")
    assert res.plugins == [] and res.warnings == []


def test_default_dir_respects_home(tmp_path: Path,
                                   monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MULTACD_HOME", str(tmp_path))
    assert default_plugin_dir() == tmp_path / ".multacd" / "plugins"
