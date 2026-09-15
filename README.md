# ⚡ multacd

**Agentic TUI untuk coding & research — dalam satu terminal.**

[![Tests](https://img.shields.io/github/actions/workflow/status/prototypeall850-creator/multacd/test.yml?branch=main&label=tests)](https://github.com/prototypeall850-creator/multacd/actions)
[![Release](https://img.shields.io/github/v/release/prototypeall850-creator/multacd?include_prereleases&label=release)](https://github.com/prototypeall850-creator/multacd/releases)
[![PyPI](https://img.shields.io/badge/PyPI-multacd-informational?logo=pypi)](https://pypi.org/project/multacd/)
[![Python](https://img.shields.io/badge/python-%E2%89%A5%203.10-blue)](https://pypi.org/project/multacd/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Satu binary, satu config BYOK. multacd bicara langsung ke API native
provider favoritmu — tanpa server perantara, tanpa langganan.
Ringan buat Termux, lengkap buat kerja harian.

```
> baca main.py lalu jelaskan cara kerjanya
■ thinking · read_file main.py ✓ 148 lines · 2.1s · 1.4k tok
  multacd adalah agentic TUI: satu loop agent dengan 39 tools…

> riset cepat: model reasoning kecil terbaik 2026
✓ web_search ×3 → web_scrape ×5 → sintesis + sumber
  …

esc membatalkan turn kapan pun · ctrl+p command palette · / untuk semua command
```

## Kenapa multacd

- **BYOK, native** — Anthropic, OpenAI, Gemini, Groq, DeepSeek, Ollama,
  atau endpoint OpenAI-compatible apa pun (`api_base`). Key via `{env:VAR}`,
  gak wajib nulis plaintext di config.
- **Dua mode fokus** — `/code` (baca, tulis, run, lint, test, git) dan
  `/research` (orchestrator quick & deep research dengan sitasi sumber).
- **39 tools built-in** — file, shell, git, web search/scrape, subagent
  task, todo, dan plugin API buat nambah sendiri.
- **Permission yang jelas** — tulis/run selalu konfirmasi dulu, baca aman
  tanpa tanya; approve per-tool (`[A]`) berlaku lintas turn; granular via
  config (`auto_approve_reads`, `ask_before_write/bash/web`).
- **Kontrol penuh di keyboard** — `esc` batalkan turn tengah jalan
  (konteks tetap valid buat turn berikutnya), `ctrl+b` background-kan
  perintah shell yang lagi jalan, inline slash palette dua kolom.
- **Kecil & jujur** — TUI murni, tanpa runtime/browser bawaan, jalan di
  Termux; meta jawaban (durasi, token) diukur beneran, bukan hiasan.
- **Tanpa cloud kami** — semua lokal: config di `~/.multacd/`,
  gak ada telemetry.

## Install

Prasyarat: Python **3.10+** (atau pakai binary standalone di bawah).

**Linux / macOS / Termux (rekomendasi):**

```bash
curl -fsSL https://raw.githubusercontent.com/prototypeall850-creator/multacd/main/scripts/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/prototypeall850-creator/multacd/main/scripts/install.ps1 | iex
```

Keduanya memasang binary standalone ke `~/.local/bin`
(atau `/usr/local/bin` kalau ada root). Tersedia untuk
linux x86_64/aarch64, macOS arm64, dan Windows (exe).

**Via pip:**

```bash
pip install "multacd==2.0.0b10"    # kanal beta v2 (pin — v2 masih prerelease)
pip install multacd                # stable v1 (1.0.0)
```

Update kapan pun: `multacd update`.

## Quickstart

```bash
cd proyek-lu
multacd
```

Setup wizard memandu 5 langkah: provider → API base URL → API key →
model → search provider (opsional). Setelah itu langsung ngobrol:

```
> perbaiki test yang gagal di tests/
> /help          semua command
> /model         ganti model kapan pun (popup)
> /connect       pasang API key provider lain tanpa restart
```

## Konfigurasi

`~/.multacd/config.yaml` — semuanya opsional, wizard yang nulis:

```yaml
model: anthropic/claude-sonnet-4-6
api_key: "{env:ANTHROPIC_API_KEY}"

# provider lain, tinggal ganti prefix:
#   openai/gpt-4o · gemini/gemini-2.0-flash · groq/llama-3.3-70b-versatile
#   deepseek/deepseek-chat · ollama/llama3.2 (butuh api_base)
# api_base: http://localhost:11434     # ollama / vLLM / endpoint OpenAI-compat
# api_key: "{env:MULTACD_KEY}"         # tanpa plaintext di file
```

Semua field + contoh per provider: [docs/configuration](docs/configuration.md).

## Dokumentasi

| | |
|---|---|
| Panduan lengkap | <https://prototypeall850-creator.github.io/multacd/> |
| Mode `/code` | [docs/modes/coding.md](docs/modes/coding.md) |
| Mode `/research` | [docs/modes/research.md](docs/modes/research.md) |
| Plugin API | [docs/plugins.md](docs/plugins.md) |
| Riwayat rilis | [CHANGELOG.md](CHANGELOG.md) |

## Status

**v2 beta** (`2.0.0b10`) — TUI dirombak total ala agentic terminal modern
(235 tes otomatis hijau di Linux/macOS/Windows × Python 3.11–3.13).
Roadmap v2 stable: multi-session + resume, MCP client, katalog agent
`.md`. Feedback & bug: [Issues](https://github.com/prototypeall850-creator/multacd/issues).

## Kontribusi

Baca [CONTRIBUTING.md](CONTRIBUTING.md) — setup dev, konvensi commit,
dan cara jalankan suite. PR kecil diterima baik.

## Lisensi

[MIT](LICENSE)
