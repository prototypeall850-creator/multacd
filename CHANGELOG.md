# Changelog

Format: Keep a Changelog. Versi: Semantic Versioning.

## [2.0.0b2] - 2026-09-12

Beta v2 kedua: cabut LiteLLM, ganti provider native (httpx, 2 adapter
SSE: OpenAI-compatible + Anthropic) — install pip Termux ringan tanpa
Rust, binary susut 91MB ke 56MB. Cost estimasi lokal ala OpenCode
tampil di info panel. Interface stream_completion tidak berubah.

Install beta: `pip install --pre "multacd==2.0.0b2"` (PyPI pre-release)
atau binary dari halaman GitHub prerelease.

## [2.0.0b1] - 2026-09-12

Beta v2 buat test Termux: redesign TUI (tanpa emoticon, responsif),
model selector, info panel, live output, token resmi, approve commit,
wizard back-nav, /copy, installer anti-diam + panduan pip Termux.

Install beta: `pip install --pre "multacd==2.0.0b1"` (PyPI pre-release)
atau binary dari halaman GitHub prerelease.

## [Unreleased] (menuju 2.0.0 — redesign v2 full bebas)

### Changed (breaking visual, config v1 tetap kebaca)
- Tema default `multacd-dark` + `multacd-light`/`multacd-min` (Termux hemat)
- Status bar compact di layar sempit, splash v2, palette fuzzy, thinking statis min-mode
- Wizard numbering /6, AskDialog responsif, marker git peach
- Wizard back-nav (Esc/tombol, fetch basi dibuang), tree reload tiap turn
- `/copy [n]` + Ctrl+Y salin jawaban (clipboard chain + fallback file)
- Live output tool, token resmi provider, approve commit + branch dialog

## [1.0.0] - 2026-09-11

Rilis stabil pertama: coding + research + personal agent dalam satu TUI,
install via binary, pip, atau source. Docs: https://prototypeall850-creator.github.io/multacd/

### Added (Phase 5 — Polish & Distribution)

- Test suite: unit + integration (`pytest tests/`), 121 tests
- Plugin system (`~/.multacd/plugins/`) + contoh + panduan
- Auto-update: cek PyPI harian, notif TUI, `multacd update`
- Entry point `multacd` via pip (`pip install -e .`), versi tunggal
- Binary PyInstaller onefile + `multacd.spec`
- Installer `scripts/install.sh` (Linux/macOS/Termux) + `install.ps1` (Windows)
- Docs MkDocs (GitHub Pages), README user-facing, CONTRIBUTING

### Added (Phase 1 — Foundation)

- Config BYOK, ReAct loop, permission auto/ask, tool dasar,
  memory SQLite, TUI Textual, cross-platform

### Added (Phase 2 — Coding Agent)

- soul.md, codebase scan, mode switching, run/lint/test,
  smart git flow, TUI widgets (tree, diff, palette, permission bar)

### Added (Phase 3 — Research Agent)

- 5 search provider BYOK, web_scrape, quick/deep research,
  sources panel (Ctrl+R), export `.md`

### Added (Phase 4 — Personal Agent)

- Bot Telegram (whitelist, konfirmasi Y/N, file up/down),
  scheduler cron persist, daily briefing + privacy filter,
  daemon mode, `/personal` di TUI

## [0.9.0] - 2026-09-11

- Pre-1.0 dev: entry point `multacd` + versi tunggal (internal, tak dirilis).
