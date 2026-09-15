# ⚡ multacd

Agentic TUI untuk coding & research — dalam satu terminal.
Satu config BYOK untuk LLM favoritmu via provider native (ringan, Termux aman).

```
> /code      baca main.py lalu jelaskan cara kerjanya
✔ read_file main.py · 148 lines
  multacd adalah agentic TUI: ...

> /research  riset cepat: model reasoning kecil terbaik 2026
✔ web_search ×3 → web_scrape ×5 → sintesis
  ...
```

> Demo di atas transkrip asli (GIF menyusul). 39 tools · 194 tests hijau.

## Install

Linux / macOS / Termux:

```bash
curl -fsSL https://raw.githubusercontent.com/prototypeall850-creator/multacd/main/scripts/install.sh | bash
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/prototypeall850-creator/multacd/main/scripts/install.ps1 | iex
```

Via pip (butuh Python 3.10+):

```bash
pip install "git+https://github.com/prototypeall850-creator/multacd"
```

> Binary rilis tersedia mulai **v1.0.0**. Sebelum itu pakai pip/git.

## Quickstart (5 menit)

```bash
multacd
```

Ikuti setup wizard (provider → API key → model), lalu:

- `/code` — coding agent (baca, tulis, run, lint, test, smart git)
- `/research` — quick & deep research ala Perplexity (BYOK search)
- `/help` — semua command · `multacd update` — update versi

## Docs

Docs lengkap (GitHub Pages): <https://prototypeall850-creator.github.io/multacd/>
Sumber: `docs/` (MkDocs). Changelog: `CHANGELOG.md`.
Kontribusi: `CONTRIBUTING.md`. Lisensi: MIT.
