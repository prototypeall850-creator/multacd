# Changelog

Format: Keep a Changelog. Versi: Semantic Versioning.

## [2.0.0b10] - 2026-09-15

Beta v2 kesepuluh — BREAKING: mode `/personal` dan seluruh stack
Telegram diangkat permanen sesuai arahan user.

- Dihapus: `tg/` (bot), `scheduler/` (cron), `daemon/` (proses
  background + IPC), `briefing/`, `tools/personal/` (7 tool), mode
  personal, CLI `--daemon` / `multacd daemon ...`, field config
  `telegram:` `schedules:` `briefing:`, step Telegram di setup wizard
  (6 → 5 langkah).
- Dependency hilang: `python-telegram-bot`, `APScheduler` → install
  jauh lebih ringan (Termux menang).
- Config lama dengan blok `telegram:` tetap aman dibaca (key asing
  diabaikan).
- Parity opencode sekaligus masuk: P1 `{env:VAR}` di config (#57),
  P4 slash palette inline dua kolom ala opencode (#58), plus
  TUI-R13 look (R13: fresh screen, logo half-block, meta rata kiri).

Install: `pip install "multacd==2.0.0b10"`.

## [2.0.0b9] - 2026-09-13

Beta v2 kesembilan (redesign TUI, tanpa ubah agent): shell layout
(session bar + sidebar responsif + footer, TUI-R1), gaya pesan chat
(aksen user + meta jawaban, TUI-R2), palette overlay + grup (TUI-R3),
provider selector popup + model overlay (TUI-R4), snapshot konteks
jujur in/out + status (TUI-R5), input adaptif layar pendek (TUI-R6).
Fix: short_workdir Windows (#41). Catatan: #44 (skills), #47 (limit/MCP).

Install: `pip install "multacd==2.0.0b9"` (tanpa --pre).

## [2.0.0b8] - 2026-09-13

Beta v2 kedelapan (refactor arsitektur, tanpa ubah fitur): kontrak event
`core/agent_events` (R2), SessionState + reducer keluar widget (R3),
AgentController + fix approve [A] lintas turn (#32, R4), widget render
dari state (R5), research sink task-scoped (R6), splash §10 lengkap (R7).

Install: `pip install "multacd==2.0.0b8"` (tanpa --pre).

## [2.0.0b7] - 2026-09-12

Beta v2 ketujuh (borongan): config key kosong dimaafkan (#27), limit jadi
tawaran Lanjut/Berhenti + stagnan outcome-aware (#28), markup crash (#29),
tavily+exa native tanpa SDK + fallback operasional (#30), key per-provider
+ /key /base (#31), splash cover + /connect + /models.

Install: `pip install "multacd==2.0.0b7"` (tanpa --pre).

## [2.0.0b6] - 2026-09-12

Beta v2 keenam — fix mode lupa ingatan (#26): system message di-refresh
tiap turn dari composer (ala opencode: system disusun ulang tiap request).
Ganti /code /research /personal sekarang beneran ganti persona yang dibaca
LLM. Install: `pip install "multacd==2.0.0b6"`.

## [2.0.0b5] - 2026-09-12

Beta v2 kelima — fix chat 2-turn 400 (#25): `add_assistant_tool_calls`
omit key `tool_calls` saat tanpa tool + `_sanitize_messages` safety net
di openai_compat. Belajar dari opencode `transform.ts` (part kosong
tidak pernah dikirim). Install: `pip install "multacd==2.0.0b5"`.

## [2.0.0b4] - 2026-09-12

Beta v2 keempat — Termux harusnya tembus sekarang (#24): `pydantic`
dibuang total (pydantic-core Rust, 0 wheel Android dari 159 rilis —
config rewrite ke dataclass + ConfigError, API konstruktor identik),
`tavily-python` jadi extra `[tavily]` (bawa tiktoken Rust),
`APScheduler<4` (kunci alpha rewrite), binary susut ke 33MB.

Install: `pip install "multacd==2.0.0b4"` (tanpa --pre, tanpa rust,
tanpa compiler — pyyaml fallback pure-python).

## [2.0.0b3] - 2026-09-12

Beta v2 ketiga — benerin install Termux (#24): `exa-py` jadi extra
opsional `[exa]` (rantai Rust jiter tanpa wheel Android), installer
langsung jalur pip di Termux (tanpa nyoba binary 404), pin beta exact
tanpa `--pre` (deps resolve stabil, anti httpx-dev/apscheduler-alpha).

Install beta: `pip install "multacd==2.0.0b3"` (tanpa --pre!)
atau binary dari halaman GitHub prerelease (Linux/macOS/Windows —
Termux wajib pip).

## [2.0.0b2] - 2026-09-12

Beta v2 kedua: cabut LiteLLM, ganti provider native (httpx, 2 adapter
SSE: OpenAI-compatible + Anthropic) — install pip Termux ringan tanpa
Rust, binary susut 91MB ke 56MB. Cost estimasi lokal ala OpenCode
tampil di info panel. Interface stream_completion tidak berubah.

Install beta: `pip install "multacd==2.0.0b2"` (tanpa --pre; pin exact
otomatis boleh beta, deps tetap stabil) atau binary dari halaman
GitHub prerelease.

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
