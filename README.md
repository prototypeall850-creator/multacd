# ⚡ multacd

Agentic TUI: **Coding Agent + Research Agent + Personal Agent** dalam satu terminal.
Satu config BYOK (Bring Your Own Key) untuk 100+ LLM provider via LiteLLM.

> Phase 1 (pondasi) — ✅ selesai. Lihat `PLAN.md` untuk roadmap Phase 2–4.

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
│  ⚡ multacd  ·  💻 coding  ·  model  ·  ● status         │  ← Status Bar
├─────────────────────────────────────────────────────────┤
│  percakapan + hasil tool (scrollable)                   │  ← Chat Panel
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

Perilaku tool:

- **Langsung jalan** (tanpa tanya): baca file/folder, `glob`, `grep`,
  semua perintah git, ingatan (`remember`/`recall`/`forget`), `todo`, `skill`.
- **Minta izin dulu** (popup Y/N/A): tulis/edit/hapus/pindah file,
  `bash`, `web_fetch`.

## Struktur project

```
multacd/
├── main.py            ← entry point
├── core/              ← config, llm_client (LiteLLM), agent_loop, permissions
├── tools/             ← filesystem, shell, git, memory, agent, web + registry
├── tui/               ← app, screens, widgets (Textual)
├── memory/            ← context (short-term) + store SQLite (long-term)
└── PLAN.md            ← panduan arah project
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

- **Phase 2** — Coding Agent penuh (codebase awareness, test, lint, sub-agent `task`)
- **Phase 3** — Research Agent (web search API, deep research ala Perplexity)
- **Phase 4** — Personal Agent (Telegram/WA gateway, scheduler, briefing harian)
