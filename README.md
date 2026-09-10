# ⚡ multacd

Agentic TUI: **Coding Agent + Research Agent + Personal Agent** dalam satu terminal.
Satu config BYOK (Bring Your Own Key) untuk 100+ LLM provider via LiteLLM.

> Phase 1 (pondasi) — ✅ selesai. Phase 2 (Coding Agent) — ✅ selesai.
> Phase 3 (Research Agent) — ✅ selesai.
> Lihat `plan/` untuk detail per phase dan `roadmap/ROADMAP.md` untuk arah besar.

---

## Syarat

- Python 3.10+
- API key dari salah satu LLM provider (Anthropic / OpenAI / Gemini / Groq / …)
  atau Ollama lokal (gratis)

## Install

```bash
git clone <repo-multacd> && cd multacd
python -m venv .venv
```

Aktifkan venv, sesuaikan OS:

| OS | Perintah |
|---|---|
| Linux / macOS / Termux | `source .venv/bin/activate` |
| Windows (PowerShell) | `.venv\Scripts\activate` |
| Windows (cmd) | `.venv\Scripts\activate.bat` |

Termux (Android) — install dulu:

```bash
pkg install python git
```

Lalu install dependencies (semua OS sama):

```bash
pip install -r requirements.txt
```

## Setup config (sekali saja)

```bash
mkdir -p ~/.multacd
```

Jalankan sekali tanpa config untuk melihat contoh lengkap:

```bash
python main.py
```

Simpan contohnya sebagai `~/.multacd/config.yaml`, isi `model` dan `api_key`
(BYOK — pakai key provider kamu). Contoh minimal:

```yaml
model: "groq/llama-3.3-70b-versatile"
api_key: "gsk_xxxx"
```

Contoh lain: `anthropic/claude-sonnet-4-6`, `openai/gpt-4o`,
`gemini/gemini-2.0-flash`, atau lokal `ollama/llama3.2`
(dengan `api_base: "http://localhost:11434"` + `api_key: "none"`).

> Catatan Windows: multacd otomatis pakai `powershell` untuk tool shell;
> Linux / macOS / Termux pakai `bash`. Semua path ditulis dengan `pathlib`,
> jadi satu codebase jalan di semua platform (wajib Windows Terminal di Windows).

## Jalankan

```bash
python main.py
```

Opsi:

```bash
python main.py --config /path/ke/config.yaml   # config custom
python main.py --model openai/gpt-4o            # override model sekali jalan
python main.py --version                        # tampilkan versi
```

## Cara pakai (TUI)

```
┌─────────────────────────────────────────────────────────┐
│  ⚡ multacd  ·  💻 code  ·  model  ·  📍 main  ·  ● status │  ← Status Bar
├──────────────┬──────────────────────────────────────────┤
│ 📁 tree      │  percakapan + hasil tool (scrollable)    │  ← Chat (+Tree)
│ (Ctrl+T)     │                                          │
├──────────────┴──────────────────────────────────────────┤
│  git diff (Ctrl+G, saat ditampilkan)                    │  ← Diff Viewer
├─────────────────────────────────────────────────────────┤
│  ❯ ketik di sini…                                       │  ← Input Bar
└─────────────────────────────────────────────────────────┘
```

| Aksi | Cara |
|---|---|
| Kirim pesan | `Enter` |
| Newline (multi-baris) | `Shift+Enter` |
| Keluar | `Ctrl+C` (2x kalau agent lagi jalan) |
| Izinkan tool | `Y` |
| Tolak tool | `N` |
| Izinkan tool itu sampai sesi habis | `A` |
| File tree (pilih file → auto-baca) | `Ctrl+T` |
| Git diff viewer | `Ctrl+G` |

Slash command (ketik di input, tanpa panggil LLM):

| Command | Fungsi |
|---|---|
| `/code` | Mode Coding Agent (default) |
| `/research` | Mode Research Agent (quick/deep research + Ctrl+R panel) |
| `/personal` | Placeholder Phase 4 |
| `/clear` | Bersihkan history |
| `/scan` | Scan ulang codebase |
| `/model [nama]` | Lihat / ganti model |
| `/soul` | Lihat kepribadian aktif |
| `/help` | Daftar command |

Perilaku tool:

- **Langsung jalan** (tanpa tanya): baca file/folder, `glob`, `grep`,
  `scan_codebase`, `lint_python` (tanpa fix), semua perintah git
  (kecuali push ke branch utama), ingatan, `todo`, `skill`.
- **Minta izin dulu** (popup Y/N/A): tulis/edit/hapus/pindah file,
  `bash`, `web_fetch`, `run_python`, `run_tests`,
  `lint_python` dengan fix, push ke `main`/`master`/….

## Struktur project

```
multacd/
├── main.py            ← entry point
├── core/              ← config, llm_client, agent_loop, permissions,
│                        mode_manager, codebase, prompt_composer
├── tools/             ← filesystem, shell, git, memory, agent, web,
│                        code (run_python/lint_python/run_tests),
│                        codebase (scan_codebase) + registry
├── tui/               ← app, screens, widgets (tree, diff, dialog)
├── memory/            ← context (short-term) + store SQLite (long-term)
├── soul.md            ← kepribadian agent (override: ~/.multacd/soul.md)
├── plan/              ← spec per phase
└── roadmap/           ← arah besar semua phase
```

Data personal (config, `memory.db`, skills) tersimpan di `~/.multacd/`
— tidak pernah di-commit ke repo.

## Troubleshooting

| Gejala | Solusi |
|---|---|
| `config belum ditemukan` | Buat `~/.multacd/config.yaml` (lihat contoh dari `python main.py`) |
| `API key ditolak` | Cek `api_key` cocok dengan provider di `model` |
| `Model tidak ditemukan` | Cek penulisan `model` (format LiteLLM, mis. `openai/gpt-4o`) |
| `Gagal konek` | Cek internet / `api_base` (khusus endpoint custom & Ollama) |
| `Rate limit (429)` | Tunggu sebentar — multacd sudah retry otomatis 3x |
| `Mencapai batas N iterasi` | Pecah tugas jadi langkah-langkah kecil |

## Roadmap

- **Phase 1** — Foundation ✅ (config BYOK, ReAct loop, 29 tools, TUI)
- **Phase 2** — Coding Agent ✅ (scan codebase, run/lint/test, smart git, 34 tools)
- **Phase 3** — Research Agent ✅ (5 search provider BYOK, quick/deep research, sources panel, 39 tools)
- **Phase 4** — Personal Agent (Telegram/WA gateway, scheduler, briefing harian)
