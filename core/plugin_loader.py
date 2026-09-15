"""Plugin loader — extend multacd tanpa fork (Phase 5 Step 2).

User taruh file Python di `~/.multacd/plugins/*.py`, multacd auto-load
saat startup. Tool dari plugin langsung tersedia untuk agent (semua
mode) dengan permission yang dideklarasikan plugin.

Format plugin (lihat plugins/example_plugin.py):
    PLUGIN_NAME = "kalender"
    PLUGIN_VERSION = "1.0.0"
    TOOL_DEFINITIONS = [{... OpenAI function schema ...}]
    TOOL_PERMISSIONS = {"nama_tool": "auto" | "ask"}  # hilang = "ask"
    def nama_tool(...) -> dict:  # nama fungsi = nama tool
        return {"success": True, "result": ..., "error": None}

Satu plugin error → di-skip + warning, plugin lain tetap load.
Tidak pernah crash startup.

Test cepat:
    python -m core.plugin_loader
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Plugin:
    """Satu plugin yang berhasil load."""

    name: str
    version: str
    description: str
    author: str
    tools: list[str] = field(default_factory=list)


@dataclass
class PluginLoadResult:
    """Hasil load_all: yang jalan + yang gagal (per-file warning)."""

    plugins: list[Plugin] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def tool_count(self) -> int:
        return sum(len(p.tools) for p in self.plugins)


def default_plugin_dir() -> Path:
    """~/.multacd/plugins — hormati MULTACD_HOME (dinamis, bukan frozen)."""
    home = Path(os.environ.get("MULTACD_HOME", str(Path.home())))
    return home / ".multacd" / "plugins"


def _validate_schema(name: str, schema: Any) -> str | None:
    """Return pesan error kalau schema tidak valid, else None."""
    if not isinstance(schema, dict):
        return f"schema `{name}` bukan dict"
    fn = schema.get("function")
    if not isinstance(fn, dict):
        return f"schema `{name}` tanpa key 'function'"
    if fn.get("name") != name:
        return f"schema `{name}`: function.name tidak cocok"
    if not fn.get("description"):
        return f"schema `{name}`: tanpa description"
    params = fn.get("parameters", {})
    if not isinstance(params, dict) or params.get("type") != "object":
        return f"schema `{name}`: parameters harus object"
    return None


def load_plugin(path: Path) -> tuple[Plugin | None, list[str]]:
    """Load satu file plugin. Return (plugin, warnings).

    plugin None = file di-skip total (import gagal / metadata invalid).
    warnings = tool yang di-skip sebagian (tabrakan nama, schema jelek).
    """
    from core.permissions import register_plugin_permission
    from tools.registry import register_tool

    warnings: list[str] = []
    try:
        spec = importlib.util.spec_from_file_location(
            f"_multacd_plugin_{path.stem}", path)
        if spec is None or spec.loader is None:
            return None, [f"{path.name}: tidak bisa diimport"]
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        return None, [f"{path.name}: gagal import ({type(e).__name__}: {e})"]

    name = getattr(mod, "PLUGIN_NAME", "")
    if not isinstance(name, str) or not name.strip():
        return None, [f"{path.name}: tanpa PLUGIN_NAME yang valid"]
    version = str(getattr(mod, "PLUGIN_VERSION", "0.0.0"))
    description = str(getattr(mod, "PLUGIN_DESCRIPTION", ""))
    author = str(getattr(mod, "PLUGIN_AUTHOR", ""))

    definitions = getattr(mod, "TOOL_DEFINITIONS", None)
    if not isinstance(definitions, list) or not definitions:
        return None, [f"{path.name}: tanpa TOOL_DEFINITIONS"]
    permissions = getattr(mod, "TOOL_PERMISSIONS", {})
    if not isinstance(permissions, dict):
        permissions = {}

    plugin = Plugin(name=name.strip(), version=version,
                    description=description, author=author)
    for schema in definitions:
        try:
            tool_name = schema["function"]["name"]
        except (KeyError, TypeError):
            warnings.append(f"{path.name}: schema tanpa function.name, di-skip")
            continue
        err = _validate_schema(tool_name, schema)
        if err is not None:
            warnings.append(f"{path.name}: {err}, di-skip")
            continue
        func = getattr(mod, tool_name, None)
        if not callable(func):
            warnings.append(f"{path.name}: fungsi `{tool_name}` tidak ada, di-skip")
            continue
        if not register_tool(tool_name, func, schema):
            warnings.append(f"{path.name}: `{tool_name}` tabrakan builtin, di-skip")
            continue
        register_plugin_permission(tool_name, permissions.get(tool_name, "ask"))
        plugin.tools.append(tool_name)

    if not plugin.tools:
        # Daftarkan kegagalan total sebagai warning pertama.
        return None, warnings or [f"{path.name}: tidak ada tool valid"]
    return plugin, warnings


def load_all(plugin_dir: Path | None = None) -> PluginLoadResult:
    """Scan & load semua plugin. Tidak pernah raise (per-file isolation)."""
    target = Path(plugin_dir) if plugin_dir is not None else default_plugin_dir()
    result = PluginLoadResult()
    if not target.is_dir():
        return result
    for path in sorted(target.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            plugin, warnings = load_plugin(path)
        except Exception as e:  # defense in depth — jangan crash startup
            result.warnings.append(f"{path.name}: error tak terduga ({e})")
            continue
        if plugin is not None:
            result.plugins.append(plugin)
        result.warnings.extend(warnings)
    return result


if __name__ == "__main__":
    import tempfile

    from tools.registry import execute_tool, unregister_tool

    with tempfile.TemporaryDirectory() as home:
        os.environ["MULTACD_HOME"] = home
        plugdir = default_plugin_dir()
        plugdir.mkdir(parents=True)
        (plugdir / "bagus.py").write_text(
            'PLUGIN_NAME = "demo"\n'
            'PLUGIN_VERSION = "1.0.0"\n'
            'TOOL_DEFINITIONS = [{"type": "function", "function": {'
            '"name": "sapa_demo", "description": "Sapa.", '
            '"parameters": {"type": "object", "properties": {}}}}]\n'
            'TOOL_PERMISSIONS = {"sapa_demo": "auto"}\n'
            'def sapa_demo() -> dict:\n'
            '    return {"success": True, "result": "halo", "error": None}\n',
            encoding="utf-8")
        (plugdir / "rusak.py").write_text("raise RuntimeError('boom')\n",
                                          encoding="utf-8")
        (plugdir / "tanpa_nama.py").write_text("X = 1\n", encoding="utf-8")
        res = load_all()
        try:
            assert len(res.plugins) == 1 and res.plugins[0].tools == ["sapa_demo"], res
            assert len(res.warnings) == 2, res.warnings  # rusak + tanpa_nama
            assert execute_tool("sapa_demo", {})["result"] == "halo"
            from core.permissions import check_permission
            assert check_permission("sapa_demo") == "auto"
        finally:
            unregister_tool("sapa_demo")
            from core.permissions import unregister_plugin_permission
            unregister_plugin_permission("sapa_demo")
            del os.environ["MULTACD_HOME"]

    print("✅ plugin_loader self-test OK (bagus load, rusak di-skip)")
