# Plugins

Taruh file Python di `~/.multacd/plugins/`, restart, tool langsung
dipakai agent. Template: `plugins/example_plugin.py` di repo.

```python
PLUGIN_NAME = "kalender"
PLUGIN_VERSION = "1.0.0"
TOOL_DEFINITIONS = [{
    "type": "function",
    "function": {
        "name": "jadwal_hari_ini",
        "description": "Ambil jadwal hari ini.",
        "parameters": {"type": "object", "properties": {}},
    },
}]
TOOL_PERMISSIONS = {"jadwal_hari_ini": "auto"}  # hilang = "ask"

def jadwal_hari_ini() -> dict:
    return {"success": True, "result": [...], "error": None}
```

Aturan: nama fungsi = `function.name`; tabrakan builtin ditolak;
tanpa permission = `"ask"`; satu file error tidak menggagalkan yang lain.
Panduan lengkap: `plugins/README.md`.
