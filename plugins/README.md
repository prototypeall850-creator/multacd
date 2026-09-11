# Plugin multacd

Extend multacd tanpa fork: taruh file Python di `~/.multacd/plugins/`,
restart multacd, tool langsung tersedia untuk agent (TUI semua mode +
Telegram, permission sama seperti tool bawaan).

## Cara cepat

```bash
mkdir -p ~/.multacd/plugins
cp plugins/example_plugin.py ~/.multacd/plugins/cuacaku.py
# edit seperlunya, restart multacd
```

Aktifkan contoh bawaan lalu cek di TUI (`/personal` atau mode apa saja):
`tanya jam berapa` → agent pakai `waktu_sekarang`.

## Field wajib

```python
PLUGIN_NAME = "namaplugin"          # wajib, string tidak kosong
PLUGIN_VERSION = "1.0.0"            # opsional (default 0.0.0)
PLUGIN_DESCRIPTION = "..."          # opsional
PLUGIN_AUTHOR = "..."               # opsional

TOOL_DEFINITIONS = [                # wajib, list tidak kosong
    {
        "type": "function",
        "function": {
            "name": "nama_tool",    # = nama fungsi di bawah
            "description": "...",   # wajib (LLM baca ini)
            "parameters": {         # wajib, type object
                "type": "object",
                "properties": {
                    "kota": {"type": "string", "description": "..."},
                },
                "required": ["kota"],
            },
        },
    }
]

TOOL_PERMISSIONS = {"nama_tool": "auto"}  # opsional; hilang = "ask"

def nama_tool(kota: str) -> dict:
    return {"success": True, "result": ..., "error": None}
```

## Aturan

- Nama fungsi **harus sama** dengan `function.name`, else tool di-skip.
- Nama tabrakan tool bawaan (`read_file`, `bash`, ...) → di-skip,
  tidak bisa bajak tool inti.
- Return selalu dict `{success, result, error}` (pakai
  `tools.common.ok()` / `fail()` biar konsisten).
- Tool tanpa entry di `TOOL_PERMISSIONS` default `"ask"` (konfirmasi dulu).
- File diawali `_` (cth `_draft.py`) diabaikan — buat nonaktifkan sementara.
- Satu file error → di-skip + warning, file lain tetap load.
  Startup tidak pernah crash gara-gara plugin.

## Debugging

- Tool tidak muncul → cek nama fungsi vs `function.name`,
  pastikan `TOOL_DEFINITIONS` tidak kosong.
- Cek warning saat startup (log TUI / `daemon logs`).
- Test manual tanpa restart TUI:

```bash
cp pluginmu.py ~/.multacd/plugins/
python -c "
from core.plugin_loader import load_all
r = load_all()
print('loaded:', [(p.name, p.tools) for p in r.plugins])
print('warnings:', r.warnings)"
```
