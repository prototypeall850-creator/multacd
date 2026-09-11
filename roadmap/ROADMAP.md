# multacd — ROADMAP.md
> Gambaran besar semua phase + panduan post-v1.0.0
> Update file ini setiap kali phase selesai atau ada rencana baru

---

## Status Overview

| Phase | Nama | Status |
|---|---|---|
| Phase 1 | Foundation | selesai |
| Phase 2 | Coding Agent | selesai |
| Phase 3 | Research Agent | selesai |
| Phase 4 | Personal Agent | selesai |
| Phase 5 | Polish & Distribution | selesai |
| v1.0.0 | Release | ✅ 2026-09-11 (PyPI + 4 binary + docs) |

---

## Phase 1 — Foundation

```
Deliverable:
  BYOK config system (~/.multacd/config.yaml)
  LiteLLM integration (semua provider)
  ReAct agent loop
  Permission system (auto-approved vs ask)
  Tool system dasar (read, write, shell, git, memory)
  Long-term memory (SQLite)
  TUI interaktif (Textual)
  Cross-platform: Linux, macOS, Windows, Termux
```

---

## Phase 2 — Coding Agent

```
Deliverable:
  soul.md system (kepribadian agent)
  Codebase awareness (auto-scan saat startup)
  Mode switching (/code, /research, /personal, /clear, /model, dll)
  run_python (jalankan kode + streaming output)
  lint_python (ruff)
  run_tests (pytest)
  Smart Git Flow (generated commit, diff preview, branch protection,
                  AI-assisted merge conflict)
  TUI: splash screen, info panel, model selector, permission bar,
       file tree (kanan), expandable tool activity, thinking indicator,
       slash command palette
```

---

## Phase 3 — Research Agent

```
Deliverable:
  Search provider system (Tavily, Exa, Brave, SerpAPI, DuckDuckGo — BYOK)
  web_scrape (fetch + clean + markdown)
  Quick Research (Perplexity-style, ~30 detik)
  Deep Research (multi-round, ~2-5 menit)
  Private tag system untuk data sensitif
  Export hasil ke .md
  /research mode aktif
  Sources Panel TUI (Ctrl+R)
```

---

## Phase 4 — Personal Agent

```
Deliverable:
  Telegram Bot (terima pesan, jalankan agent, kirim balik)
  Access control (admin, user, stranger) dengan /userbaru command
  File handling level 3 (terima & kirim file via Telegram)
  Cron scheduler (APScheduler, persist SQLite)
  Daily briefing (todo + berita + git status, privacy terlindungi)
  Private tag system ([private] tidak pernah keluar ke LLM)
  Daemon mode (jalan di background tanpa TUI)
  /personal mode di TUI
```

---

## Phase 5 — Polish & Distribution

```
Deliverable:
  Test suite (unit + integration)
  CI/CD (GitHub Actions: test, build binary, release)
  Plugin system (~/.multacd/plugins/)
  Auto-update (cek PyPI, notif kalau ada versi baru)
  PyInstaller binary (Linux x86_64, Linux ARM64, macOS Intel,
                       macOS Apple Silicon, Windows, Termux)
  Installer: install.sh (Linux/macOS/Termux), install.ps1 (Windows)
  pip install multacd
  README.md + demo GIF
  CHANGELOG.md
  CONTRIBUTING.md
  Docs site (GitHub Pages + MkDocs)
  GitHub templates (issue + PR)
  MIT License
```

---

## v1.0.0

```
Semua Phase 1-5 selesai.
Semua platform terinstall dan tertest.
Dokumentasi lengkap.
Repo public, CI/CD jalan.

Install:
  Linux/macOS/Termux : curl -fsSL https://get.multacd.dev | bash
  Windows            : irm https://get.multacd.dev/install.ps1 | iex
  pip                : pip install multacd
```

---

## Panduan Post-v1.0.0

### Dokumen yang Tetap Hidup

```
ROADMAP.md   → planning fitur baru (update di sini)
DESIGN.md    → keputusan desain/TUI (update kalau ada perubahan UI)
CHANGELOG.md → track tiap versi (isi tiap release)
```

### Dokumen yang Boleh Dihapus Setelah Dipakai

```
PLAN.md, PLAN-phase2.md, PLAN-phase3.md,
PLAN-phase4.md, PLAN-phase5.md

Tugasnya sudah selesai — informasinya sudah "pindah" ke kode.
Hapus untuk menjaga repo tetap bersih.
Kalau mau disimpan sebagai arsip → pindah ke folder /archive/
```

### Workflow untuk Fitur Baru (post v1.0.0)

```
1. Tulis ide di ROADMAP.md → section "Planned"
2. Kalau fitur kecil (1-3 hari) → langsung buat branch + PR
3. Kalau fitur besar → buat PLAN-namafitur.md dulu
4. Kalau ada perubahan UI/TUI → update DESIGN.md dulu
5. Setelah merge → pindah dari "Planned" ke versi yang tepat di ROADMAP
6. Update CHANGELOG.md
7. Tag versi baru → CI/CD handle sisanya
```

### Semantic Versioning

```
v1.0.x   → bug fixes (patch)
           Contoh: v1.0.1, v1.0.2
           Tidak ada fitur baru, hanya perbaikan

v1.x.0   → fitur baru, backward-compatible (minor)
           Contoh: v1.1.0, v1.2.0
           Tambah fitur tanpa merusak yang sudah ada

vx.0.0   → breaking changes (major)
           Contoh: v2.0.0
           Config format berubah, tool API berubah, dll
```

---

## Planned — Post v1.0.0

> Catat ide fitur di sini. Belum ada komitmen kapan dikerjakan.

```
Fitur yang mungkin masuk v1.1.0:
  WhatsApp gateway (via whatsapp-web.py)
  Weather integration untuk daily briefing
  Google Calendar integration (via plugin)
  More themes (Tokyo Night, Nord, Dracula)

Fitur yang mungkin masuk v1.2.0:
  LSP integration (Language Server Protocol) untuk coding agent
  Multi-project workspace (bisa kelola beberapa project sekaligus)
  Voice input (via Whisper API)

Fitur yang mungkin masuk v2.0.0:
  Plugin marketplace (cari & install plugin dari registry online)
  Team mode (shared agent untuk beberapa user di jaringan yang sama)
```

---

*multacd ROADMAP.md*
*Update status dan planned features di sini.*
*Untuk detail implementasi, buat PLAN-namafitur.md.*
