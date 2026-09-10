# multacd — ROADMAP.md
> Gambaran besar semua phase dari awal sampai selesai
> Diupdate setiap selesai satu phase

---

## Status Overview

| Phase | Nama | Status |
|---|---|---|
| Phase 1 | Foundation | ✅ Selesai |
| Phase 2 | Coding Agent | ✅ Selesai |
| Phase 3 | Research Agent | 📋 Planned |
| Phase 4 | Personal Agent | 📋 Planned |
| Phase 5 | Polish & Distribution | 📋 Planned |

---

## Phase 1 — Foundation ✅

**Tujuan:** Pondasi yang ketiga mode agent berdiri di atasnya.

```
Deliverable:
  ✅ BYOK config system (~/.multacd/config.yaml)
  ✅ LiteLLM integration (semua provider)
  ✅ ReAct agent loop
  ✅ Permission system (auto-approved vs ask)
  ✅ Tool system dasar (read, write, shell, git, memory)
  ✅ Long-term memory (SQLite)
  ✅ TUI interaktif (Textual)
  ✅ Cross-platform: Linux, macOS, Windows, Termux
```

---

## Phase 2 — Coding Agent ✅

**Tujuan:** multacd jadi AI coding partner yang ngerti project kamu.

```
Deliverable:
  ✅ Codebase awareness (auto-scan saat startup)
  ✅ Deteksi jenis project (Python, Node, dll)
  ✅ Code execution — Python (run, capture output, timeout)
     ⏳ streaming output real-time → issue #3
  ✅ Linting — ruff (check + auto-fix)
  ✅ Testing — pytest (run all / run specific)
  ✅ Smart Git Flow:
        auto git_status saat startup
        LLM generate conventional commit message (prompt-driven)
        ⏳ diff preview + dialog approve sebelum commit → issue #4
        branch protection untuk main/master (tool-level)
        AI-assisted merge conflict resolution (tool + prompt)
  ✅ Mode switching (/code, /research, /personal, /clear, /scan, /model, /help, /soul)
  ✅ TUI enhancement:
        file tree panel (toggle Ctrl+T)
        git status di status bar (branch + changed files)
        diff viewer dengan syntax highlight (toggle Ctrl+G)
        ⏳ progress indicator live saat scan/test → issue #3

Tools baru di Phase 2 (29 → 34):
  run_python     jalankan file Python atau snippet
  lint_python    lint dengan ruff, tampilkan error per baris
  run_tests      jalankan pytest, tampilkan hasil per test
  scan_codebase  scan & generate project context
  git_merge      merge + lapor conflict ours-vs-theirs
```

**Estimasi kompleksitas:** Sedang — tools baru tapi pattern sama dengan Phase 1.

---

## Phase 3 — Research Agent 📋

**Tujuan:** multacd bisa riset mendalam seperti Perplexity, multi-sumber, terstruktur.

```
Deliverable:
  [ ] Web search integration:
        Brave Search API (rekomendasi utama, privacy-friendly)
        SerpAPI sebagai fallback
        Konfigurasi di config.yaml (pilih provider)
  [ ] Web scraping:
        httpx + BeautifulSoup untuk extract konten
        Handle paywall & javascript-heavy sites (fallback graceful)
        Respect robots.txt
  [ ] Deep Research Mode:
        Multi-step search (satu query → temukan → follow-up query)
        Cross-reference antar sumber
        Detect & flag informasi yang kontradiktif antar sumber
        Auto-generate follow-up questions
  [ ] Synthesis & Summary:
        Summarize per sumber → gabungkan jadi satu narasi
        Format output: bisa markdown, bullet, atau essay
        Kutipan & sumber tercantum jelas
        Export hasil ke file .md
  [ ] Mode /research di TUI:
        Panel khusus untuk tampilkan sumber yang ditemukan
        Progress indicator (step 1/5: searching... step 2/5: reading...)
        Preview sumber sebelum di-scrape
  [ ] Web fetch yang sudah ada di Phase 1 → diperdalam

Tools baru di Phase 3:
  web_search       cari dengan Brave/SerpAPI, return top N hasil
  web_scrape       extract konten bersih dari URL
  deep_research    orkestrasi multi-step research
  export_research  simpan hasil riset ke file .md
```

**Estimasi kompleksitas:** Sedang-Tinggi — perlu API eksternal (Brave/Serp), multi-step orchestration lebih kompleks.

**Dependency tambahan:**
```
brave-search       # atau serpapi
beautifulsoup4     # web scraping
markdownify        # convert HTML ke markdown
```

---

## Phase 4 — Personal Agent 📋

**Tujuan:** multacd bisa dikontrol dari mana saja, bukan hanya dari terminal.

```
Deliverable:
  [ ] Telegram Gateway:
        Bot yang bisa terima perintah dari Telegram
        Jalankan agent loop di background
        Kirim hasil balik ke Telegram (teks, file, code block)
        Support perintah /start, /stop, /status
        Keamanan: whitelist user ID yang boleh akses
  [ ] WhatsApp Gateway:
        Integrasi via WhatsApp Business API atau library
        Fungsionalitas sama seperti Telegram
        (Catatan: lebih tricky dari Telegram, perlu nomor WA dedicated)
  [ ] Background Scheduler:
        Cron-style job scheduler
        Contoh: setiap pagi jam 7 → kirim briefing ke Telegram
        Definisikan jadwal di config.yaml
  [ ] Daily Briefing:
        Auto-generate ringkasan harian
        Bisa include: todo list, reminder, summary project
        Kirim ke Telegram/WA sesuai jadwal
  [ ] Mode /personal di TUI:
        Lihat status bot (aktif/nonaktif)
        Lihat log percakapan dari Telegram/WA
        Kelola scheduled jobs
  [ ] Persistent background process:
        multacd bisa jalan sebagai daemon di background
        Tidak perlu TUI terbuka terus
        Kontrol via: systemd (Linux), launchd (macOS), Task Scheduler (Windows)

Tools baru di Phase 4:
  send_telegram    kirim pesan ke Telegram
  send_whatsapp    kirim pesan ke WhatsApp
  schedule_job     tambah/hapus scheduled task
  get_jobs         lihat semua scheduled task
  daemon_start     jalankan multacd sebagai background process
  daemon_stop      hentikan background process
```

**Estimasi kompleksitas:** Tinggi — perlu setup bot, background process, keamanan akses.

**Dependency tambahan:**
```
python-telegram-bot    # Telegram bot
schedule               # job scheduler
```

**Catatan WhatsApp:**
WhatsApp lebih kompleks dari Telegram. Opsi:
- `whatsapp-web.py` (unofficial, butuh scan QR)
- WhatsApp Business API (official, butuh akun bisnis)
- Recommend: mulai Telegram dulu, WA belakangan.

---

## Phase 5 — Polish & Distribution 📋

**Tujuan:** multacd siap dipakai orang lain, bukan hanya kamu.

```
Deliverable:
  [ ] Installer satu perintah:
        Linux/macOS : curl -fsSL install.sh | bash
        Windows     : PowerShell script
        Termux      : satu baris command
  [ ] Auto-update mechanism:
        Cek versi baru saat startup (sekali sehari)
        Notifikasi kalau ada update
        Perintah: multacd update
  [ ] Plugin system:
        User bisa tambah tool custom
        Format: file Python di ~/.multacd/plugins/
        multacd auto-load saat startup
  [ ] Documentation:
        Docs lengkap di GitHub
        GIF demo di README
        Contoh use case per mode
  [ ] Packaging:
        Publish ke PyPI: pip install multacd
        Bisa langsung: python -m multacd
  [ ] Testing:
        Unit test per tool
        Integration test untuk agent loop
        CI/CD dengan GitHub Actions
  [ ] Theming:
        Lebih dari sekedar dark/light
        Custom color scheme di config.yaml
```

**Estimasi kompleksitas:** Rendah-Sedang — ini polish, bukan fitur baru besar.

---

## Dependency Master List

```
Phase 1 (sudah install):
  textual, litellm, pyyaml, pydantic, httpx

Phase 2 (tambahan, sudah install):
  ruff, pytest
  (gitpython TIDAK jadi dipakai — git via subprocess, tanpa dep baru)

Phase 3 (tambahan):
  beautifulsoup4, markdownify
  + pilih salah satu search API:
    brave-search ATAU serpapi

Phase 4 (tambahan):
  python-telegram-bot, schedule

Phase 5 (tambahan):
  pytest (sudah ada Phase 2), build, twine
```

---

## Evolusi Struktur Folder

```
Phase 1:
  core/, tools/, tui/, memory/

Phase 2 (tambahan):
  tools/code/        → run_python, lint_python, run_tests
  tools/codebase/    → scan_codebase, project_context

Phase 3 (tambahan):
  tools/research/    → web_search, web_scrape, deep_research

Phase 4 (tambahan):
  tools/messaging/   → send_telegram, send_whatsapp
  tools/scheduler/   → schedule_job, get_jobs
  daemon/            → background process handler

Phase 5 (tambahan):
  plugins/           → user plugin directory
  tests/             → semua unit & integration test
  docs/              → dokumentasi
```

---

## Prinsip yang Dijaga di Semua Phase

```
1. Cross-platform          → Linux, macOS, Windows, Termux
2. BYOK                    → user selalu bawa API key sendiri
3. Config di ~/.multacd/   → project folder tetap bersih
4. Permission system       → agent tidak bisa seenaknya
5. Streaming real-time     → tidak nunggu, langsung tampil
6. Error messages friendly → tidak ada traceback mentah
7. Graceful degradation    → kalau satu fitur gagal,
                             sisanya tetap jalan
```

---

*multacd ROADMAP.md*
*Update status setiap kali selesai satu phase.*
