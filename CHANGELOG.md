# Changelog

Format: Keep a Changelog. Versi: Semantic Versioning.

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
