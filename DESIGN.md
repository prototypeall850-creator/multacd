# multacd — DESIGN.md
> Keputusan desain UX/UI yang berlaku di semua phase
> Dibuat sebelum Phase 3 — berlaku retroaktif ke Phase 2 TUI

---

## Daftar Isi

1. [Icon System](#1-icon-system)
2. [Theme & Color Palette](#2-theme--color-palette)
3. [Layout TUI](#3-layout-tui)
4. [Compact Confirmation Popup](#4-compact-confirmation-popup)
5. [Expandable Tool Activity](#5-expandable-tool-activity)
6. [Thinking Indicator](#6-thinking-indicator)
7. [Slash Command Palette](#7-slash-command-palette)
8. [Setup Wizard (First Run)](#8-setup-wizard-first-run)
9. [Instalasi (Phase 5)](#9-instalasi-phase-5)

---

## 1. Icon System

Tiga level icon dengan fallback otomatis:

### Level 1 — Nerd Fonts (default)
Dipakai kalau terminal support Nerd Fonts.
Ini standar tools TUI modern: lazygit, btop, Neovim, Starship.

```
  folder          git branch      python
  search          terminal        check
  error           warning         settings
```

### Level 2 — Unicode Symbols (fallback)
Dipakai kalau Nerd Fonts tidak terdeteksi.
Support di semua terminal modern tanpa install tambahan.

```
Symbol    Arti
  *       aktif / bullet
  >       prompt / arrow
  +       tambah / expand
  -       kurangi / collapse
  @       branch / user
  #       section
  !       warning
  x       error
  ~       home / tilde
  ..      loading / thinking
  |       separator
  []      bracket untuk label
```

### Level 3 — ASCII Murni (ultimate fallback)
Untuk Termux lama atau terminal yang sangat terbatas.

```
[OK]  [!!]  [..]  [>>]  [**]
```

### Deteksi Otomatis

```
Saat startup:
  1. Cek environment variable TERM, COLORTERM
  2. Tulis karakter Nerd Fonts ke terminal
  3. Cek apakah render width-nya benar
  4. Kalau ya → pakai Nerd Fonts
  5. Kalau tidak → cek Unicode support
  6. Kalau tidak → fallback ASCII

User bisa override di config.yaml:
  icon_style: "nerdfonts"   # nerdfonts | unicode | ascii
```

---

## 2. Theme & Color Palette

### Default Theme: Catppuccin Mocha (Dark)

Alasan dipilih:
- Palette yang paling matang di komunitas terminal
- Dipakai oleh btop, lazygit, Neovim, Starship, Alacritty, dll
- Contrast ratio yang tepat — tidak terlalu terang, tidak terlalu gelap
- Ada varian light (Catppuccin Latte) untuk yang prefer light mode
- Open source, terdokumentasi dengan baik

#### Palette Utama

```
Nama        Hex         Dipakai untuk
─────────── ─────────── ─────────────────────────────────
Base        #1e1e2e     Background utama TUI
Mantle      #181825     Background panel yang lebih dalam
Crust       #11111b     Background paling gelap (border area)
Surface 0   #313244     Background widget / card
Surface 1   #45475a     Background hover / selected
Surface 2   #585b70     Background disabled
Overlay 0   #6c7086     Teks sangat redup (placeholder)
Overlay 1   #7f849c     Teks redup (subtext)
Overlay 2   #9399b2     Teks sedang
Subtext 0   #a6adc8     Teks sekunder
Subtext 1   #bac2de     Teks sekunder lebih terang
Text        #cdd6f4     Teks utama

Green       #a6e3a1     Sukses, /code mode, approved
Blue        #89b4fa     Info, /research mode, link
Mauve       #cba6f7     Accent, /personal mode
Yellow      #f9e2af     Warning, pending
Red         #f38ba8     Error, denied, delete
Peach       #fab387     Git modified
Teal        #94e2d5     Git new/untracked
Sapphire    #74c7ec     Tool running
Lavender    #b4befe     Highlight
```

#### Warna per Mode

```
/code      Green   #a6e3a1    status bar label warna hijau
/research  Blue    #89b4fa    status bar label warna biru
/personal  Mauve   #cba6f7    status bar label warna ungu
```

#### Warna Status Tool

```
Tool antri      Overlay 1   #7f849c    redup
Tool running    Sapphire    #74c7ec    biru muda
Tool sukses     Green       #a6e3a1    hijau
Tool gagal      Red         #f38ba8    merah
Tool dibatalkan Yellow      #f9e2af    kuning
```

#### Warna Git

```
Modified     Peach   #fab387
New/Add      Teal    #94e2d5
Deleted      Red     #f38ba8
Renamed      Blue    #89b4fa
Conflict     Yellow  #f9e2af
```

### Variant Theme Lain

```
Tersedia di config.yaml → theme:
  catppuccin-mocha    (default, dark)
  catppuccin-latte    (light variant)
  catppuccin-frappe   (medium dark)
  catppuccin-macchiato (dark, lebih warm)
```

Phase 5 bisa tambah: Tokyo Night, Nord, Dracula — tapi Catppuccin dulu.

### Implementasi di Textual

```python
# tui/themes/catppuccin_mocha.py
THEME = {
    "background": "#1e1e2e",
    "surface": "#313244",
    "text": "#cdd6f4",
    "subtext": "#a6adc8",
    "success": "#a6e3a1",
    "error": "#f38ba8",
    "warning": "#f9e2af",
    "info": "#89b4fa",
    "accent": "#cba6f7",
    # ... dst
}
```

---

## 3. Layout TUI

### Layout Dasar (tanpa panel tambahan)

```
┌──────────────────────────────────────────────────────┐
│  multacd   code   claude-sonnet-4-6   main +3   [*]  │  Status Bar
├──────────────────────────────────────────────────────┤
│                                                      │
│                                                      │
│   [Chat Panel]                                       │
│   Scrollable, full width                             │
│   Render markdown, code blocks, tool activity        │
│                                                      │
│                                                      │
├──────────────────────────────────────────────────────┤
│  thinking.......                                     │  Thinking Bar
├──────────────────────────────────────────────────────┤
│  > _                                                 │  Input Bar
└──────────────────────────────────────────────────────┘
```

### Layout dengan File Tree (Ctrl+T)

```
┌──────────────────────────────────────────────────────┐
│  multacd   code   claude-sonnet-4-6   main +3   [*]  │  Status Bar
├───────────────────────────────────┬──────────────────┤
│                                   │  myapp/          │
│   [Chat Panel]                    │  ├ core/         │
│                                   │  │ ├ config.py   │
│   Render markdown, code blocks,   │  │ └ agent..     │
│   tool activity, dll              │  ├ tools/        │
│                                   │  ├ tui/          │
│                                   │  └ main.py       │  File Tree
├───────────────────────────────────┴──────────────────┤
│  thinking.......                                     │  Thinking Bar
├──────────────────────────────────────────────────────┤
│  > _                                    Ctrl+T tree  │  Input Bar
└──────────────────────────────────────────────────────┘

File tree posisi: KANAN
Toggle: Ctrl+T
Width: ~25% dari total lebar terminal
```

### Layout /research dengan Sources Panel (Ctrl+R)

```
┌──────────────────────────────────────────────────────┐
│  multacd  research  claude-sonnet-4-6    [*]         │  Status Bar
├───────────────────────────────────┬──────────────────┤
│                                   │  Sources (8)     │
│                                   │  ──────────────  │
│                                   │  * arxiv.org     │
│   [Chat Panel]                    │  * nature.com    │
│                                   │  > ieee.org      │
│                                   │  . wired.com     │
│                                   │  ──────────────  │
│                                   │  Round: 2 / 5    │
│                                   │  Read: 6         │
│                                   │  [Export .md]    │  Sources Panel
├───────────────────────────────────┴──────────────────┤
│  thinking.......                                     │  Thinking Bar
├──────────────────────────────────────────────────────┤
│  > _                                    Ctrl+R panel │  Input Bar
└──────────────────────────────────────────────────────┘

Sources panel posisi: KANAN
Toggle: Ctrl+R
Hanya muncul di mode /research
```

### Status Bar Detail

```
┌──────────────────────────────────────────────────────┐
│  multacd   code   claude-sonnet-4-6   main +3   [*]  │
│     [1]     [2]         [3]             [4]      [5] │
└──────────────────────────────────────────────────────┘

[1] Nama app          → selalu "multacd"
[2] Mode aktif        → "code" / "research" / "personal"
                        warna sesuai mode
[3] Model aktif       → dari config, update saat /model
[4] Git info          → "main +3" (branch + modified count)
                        "no git" kalau bukan repo
                        tidak muncul kalau tidak relevan
[5] Status agent      → [*] idle, [>] thinking, [!] error
```

---

## 4. Compact Confirmation Popup

### Desain Lama (dihapus)
Modal besar di tengah layar — terlalu interrupt.

### Desain Baru — Satu Baris di Atas Input

```
Sebelum (idle):
┌──────────────────────────────────────────────────────┐
│  thinking.......                                     │
├──────────────────────────────────────────────────────┤
│  > _                                                 │
└──────────────────────────────────────────────────────┘

Saat ada permission request:
┌──────────────────────────────────────────────────────┐
│  write_file  src/utils/helper.py       Y   N   A    │  ← Permission Bar
├──────────────────────────────────────────────────────┤
│  > _                                                 │
└──────────────────────────────────────────────────────┘
```

### Spesifikasi

```
Posisi    : Tepat di atas input bar, gantikan thinking bar sementara
Tinggi    : 1 baris
Warna bg  : Surface 0 (#313244) — sedikit lebih terang dari background
Warna teks: Text (#cdd6f4)
Highlight : Nama tool (Sapphire), path file (Subtext 1)

Tombol:
  Y → izinkan sekali ini
  N → tolak
  A → izinkan semua untuk sesi ini (only for ASK tools)

Navigasi:
  Y / y / Enter     → pilih Y
  N / n / Escape    → pilih N
  A / a             → pilih A

Kalau tool = delete_file → tambah satu karakter warning:
  delete_file  src/old.py   ! permanent     Y   N
```

### Untuk Operasi Berisiko Tinggi (delete, push ke main)

Tetap satu baris, tapi ada marker "!" dan warna merah:

```
┌──────────────────────────────────────────────────────┐
│  ! delete_file  src/critical.py   permanent    Y   N │  ← warna merah
├──────────────────────────────────────────────────────┤
│  > _                                                 │
└──────────────────────────────────────────────────────┘
```

---

## 5. Expandable Tool Activity

### Konsep
Setiap tool call di chat panel bisa di-collapse atau expand.
Default: collapsed (satu baris ringkas).
User expand kalau mau lihat detail.

### Tampilan Collapsed

```
  > write_file  src/utils/helper.py                [+]
  > grep  "def run"  core/                         [+]
  > git_commit  feat: tambah mode switching        [+]
```

### Tampilan Expanded (tekan Enter atau klik [+])

```
  v write_file  src/utils/helper.py                [-]
    Created file (47 lines)
    ────────────────────────────────
    + def load_config(path: Path):
    +     with open(path) as f:
    +         return yaml.safe_load(f)
    + 
    + def validate_config(config):
    ...

  v grep  "def run"  core/                         [-]
    3 matches found
    ────────────────────────────────
    core/agent_loop.py:42    def run(self, input):
    core/agent_loop.py:89    def run_tool(self, name, params):
    core/mode_manager.py:15  def run_command(self, cmd):

  v git_commit  feat: tambah mode switching        [-]
    3 files committed
    ────────────────────────────────
    M  core/agent_loop.py
    A  core/mode_manager.py
    M  requirements.txt
```

### Expandable Thinking / Reasoning

```
Collapsed (default):
  v thinking                                        [+]

Expanded:
  v thinking                                        [-]
    ────────────────────────────────
    User minta buat fungsi load_config. File belum ada,
    jadi perlu write_file. Path yang paling logis adalah
    core/config.py. Perlu import yaml dan pathlib.
    Akan buat fungsi dengan error handling yang proper...
    ────────────────────────────────
```

> Thinking hanya tampil kalau LLM provider support reasoning/thinking
> (contoh: claude-3-7-sonnet dengan extended thinking, o3, dll)
> Kalau provider tidak support → bagian thinking tidak muncul sama sekali

### Implementasi di Textual

```
Pakai Textual CollapsibleWidget atau custom widget:
  class ToolActivity(Widget):
    collapsed: bool = True
    tool_name: str
    tool_result: dict

    def toggle(self):
      self.collapsed = not self.collapsed
      self.refresh()
```

---

## 6. Thinking Indicator

### Posisi
Di antara Chat Panel dan Input Bar.
Satu baris tipis, tidak ada border.

### Tampilan

```
Saat idle (tidak ada apa-apa):
  [baris kosong]

Saat agent thinking:
  thinking.......

Saat agent jalankan tool:
  running write_file...

Saat agent search (Phase 3):
  searching arxiv.org...

Saat scan codebase:
  scanning project...

Saat run tests:
  running tests...
```

### Animasi Titik-Titik

```
thinking.
thinking..
thinking...
thinking....
thinking.....
thinking......
thinking.......
thinking.       ← loop kembali
```

Interval: 200ms per titik, loop 7 titik lalu reset.

### Warna
```
Teks    : Overlay 1 (#7f849c) — redup, tidak mencolok
Posisi  : Left-aligned, padding kiri sama dengan input bar
```

---

## 7. Slash Command Palette

### Trigger
Ketik `/` di input bar → palette muncul tepat di atas input bar.

### Tampilan

```
Saat user ketik "/":
┌──────────────────────────────────────────────────────┐
│  /clear      Clear conversation                      │
│  /code       Switch to Coding Agent mode             │
│  /help       Show all commands                       │
│  /model      Switch LLM model                       │
│  /personal   Switch to Personal Agent mode           │
│  /research   Switch to Research Agent mode           │
│  /scan       Re-scan codebase                        │
│  /soul       Show active soul.md                     │
├──────────────────────────────────────────────────────┤
│  thinking.......                                     │
├──────────────────────────────────────────────────────┤
│  > / _                                               │
└──────────────────────────────────────────────────────┘

Saat user ketik "/mo":
┌──────────────────────────────────────────────────────┐
│  /model      Switch LLM model                        │  ← filtered
├──────────────────────────────────────────────────────┤
│  thinking.......                                     │
├──────────────────────────────────────────────────────┤
│  > /mo _                                             │
└──────────────────────────────────────────────────────┘
```

### Navigasi Palette

```
Ketik /         → buka palette, tampilkan semua command
Ketik /mo       → filter real-time, tampilkan yang cocok
Arrow Up/Down   → navigasi item
Enter           → pilih command
Escape          → tutup palette, kembali ke input normal
Tab             → autocomplete command ke input bar
```

### Style Palette

```
Background  : Surface 0 (#313244)
Border      : Surface 2 (#585b70), tipis
Item hover  : Surface 1 (#45475a)
Command     : Text (#cdd6f4)  
Description : Subtext 0 (#a6adc8), redup
Filter match: Lavender (#b4befe), highlight bagian yang match
```

### Command yang Tersedia di Palette

```
Command         Deskripsi                           Phase
/code           Switch to Coding Agent mode         2
/research       Switch to Research Agent mode       3
/personal       Switch to Personal Agent mode       4
/clear          Clear conversation history          1
/scan           Re-scan codebase                    2
/model [name]   Switch LLM model                   2
/help           Show all commands                   1
/soul           Show active soul.md                 2
```

---

## 8. Setup Wizard (First Run)

### Trigger
Saat `python main.py` dijalankan pertama kali dan
`~/.multacd/config.yaml` belum ada.

### Flow Lengkap

```
Step 1 — Welcome Screen
┌──────────────────────────────────────────────────────┐
│                                                      │
│              Welcome to multacd                      │
│         Agentic TUI for coding & research            │
│                                                      │
│   Config belum ditemukan di ~/.multacd/config.yaml   │
│   Mari setup dalam beberapa langkah.                 │
│                                                      │
│                    [ Continue ]                      │
│                                                      │
└──────────────────────────────────────────────────────┘

Step 2 — Pilih Provider
┌──────────────────────────────────────────────────────┐
│  Setup (1/4) — LLM Provider                          │
│                                                      │
│  Pilih provider:                                     │
│                                                      │
│  > Anthropic                                         │
│    OpenAI                                            │
│    Google Gemini                                     │
│    Groq                                              │
│    Ollama (local)                                    │
│    Custom (OpenAI-compatible)                        │
│                                                      │
│  Arrow Up/Down untuk navigasi, Enter untuk pilih     │
└──────────────────────────────────────────────────────┘

Step 3 — API Base URL
┌──────────────────────────────────────────────────────┐
│  Setup (2/4) — API Base URL                          │
│                                                      │
│  Base URL untuk Anthropic:                           │
│  (kosongkan untuk default)                           │
│                                                      │
│  > https://api.anthropic.com  _                      │
│                                                      │
│  Enter untuk lanjut, Ctrl+C untuk batal              │
└──────────────────────────────────────────────────────┘

Step 4 — API Key
┌──────────────────────────────────────────────────────┐
│  Setup (3/4) — API Key                               │
│                                                      │
│  Masukkan API key untuk Anthropic:                   │
│  (karakter disembunyikan)                            │
│                                                      │
│  > ****************************_                     │
│                                                      │
│  Enter untuk lanjut                                  │
└──────────────────────────────────────────────────────┘

Step 4b — Fetch & Pilih Model
┌──────────────────────────────────────────────────────┐
│  Setup (4/4) — Model                                 │
│                                                      │
│  Fetching available models...                        │
│                                                      │
│  Pilih model:                                        │
│                                                      │
│  > claude-sonnet-4-6     (recommended)               │
│    claude-opus-4                                     │
│    claude-haiku-4-5                                  │
│                                                      │
│  Arrow Up/Down, Enter untuk pilih                    │
└──────────────────────────────────────────────────────┘

Step 5 — Konfirmasi & Simpan
┌──────────────────────────────────────────────────────┐
│  Setup selesai                                       │
│                                                      │
│  Provider  : Anthropic                               │
│  Model     : claude-sonnet-4-6                       │
│  Config    : ~/.multacd/config.yaml                  │
│                                                      │
│  [ Simpan & Mulai ]       [ Ulangi Setup ]           │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Kalau Fetch Model Gagal (key salah / tidak ada koneksi)

```
┌──────────────────────────────────────────────────────┐
│  Setup (4/4) — Model                                 │
│                                                      │
│  ! Tidak bisa fetch model list                       │
│    Pastikan API key benar dan ada koneksi internet   │
│                                                      │
│  Masukkan nama model secara manual:                  │
│  > claude-sonnet-4-6 _                               │
│                                                      │
│  Atau: [ Kembali ke Step 3 ]                         │
└──────────────────────────────────────────────────────┘
```

### Implementasi

```
tui/screens/setup_wizard.py
  class SetupWizard(Screen):
    step: int = 1
    provider: str
    api_base: str
    api_key: str
    model: str

    def next_step()
    def prev_step()
    def fetch_models()    → async, panggil LiteLLM
    def save_config()     → tulis ke ~/.multacd/config.yaml
```

---

## 9. Instalasi (Phase 5)

Didokumentasikan di sini sejak awal supaya struktur project
sudah siap saat Phase 5 tiba.

### Linux, macOS, Termux

```bash
curl -fsSL https://get.multacd.dev | bash
```

Script bash melakukan:
```
1. Deteksi OS dan package manager
2. Install Python 3.11+ kalau belum ada
3. Install multacd via pip: pip install multacd
4. Verifikasi instalasi: multacd --version
5. Print instruksi singkat cara mulai
```

### Windows

```powershell
irm https://get.multacd.dev/install.ps1 | iex
```

Script PowerShell melakukan:
```
1. Cek Python 3.11+ tersedia
2. Install via pip: pip install multacd
3. Verifikasi: multacd --version
4. Print instruksi cara mulai
```

### Via pip (alternatif, lebih sederhana)

```bash
pip install multacd
multacd
```

### Struktur yang Harus Siap dari Sekarang

```
multacd/
  scripts/
    install.sh       ← bash installer (Linux/macOS/Termux)
    install.ps1      ← PowerShell installer (Windows)
  pyproject.toml     ← config untuk publish ke PyPI
                       definisikan: entry point = multacd = main:app
```

### Entry Point di pyproject.toml

```toml
[project.scripts]
multacd = "main:app"
```

Setelah install, user cukup ketik `multacd` di terminal — tidak perlu
`python main.py` lagi.

---

## Ringkasan — Berlaku di Phase Mana

```
Keputusan                    Mulai berlaku
─────────────────────────── ─────────────
Icon system (Nerd Fonts)    Phase 2 (update TUI)
Catppuccin theme            Phase 2 (update TUI)
Layout (file tree kanan)    Phase 2 (update TUI)
Compact confirmation        Phase 2 (update TUI)
Expandable tool activity    Phase 2 (update TUI)
Thinking indicator          Phase 2 (update TUI)
Slash command palette       Phase 2 (update TUI)
Setup wizard                Phase 2 (gantikan config manual)
Sources panel               Phase 3 (/research)
Instalasi curl/irm          Phase 5
```

---

*multacd DESIGN.md*
*Keputusan di sini tidak diubah tanpa alasan kuat.*
*Konsistensi adalah kunci UX yang baik.*


---

## 10. Splash Screen (Tampilan Awal)

Ditampilkan saat multacd pertama dibuka, sebelum user mengetik apapun.
Terinspirasi dari OpenCode — bersih, terpusat, minimal.

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                                                             │
│                                                             │
│                    m u l t a c d                            │
│                  (ASCII art / besar)                        │
│                                                             │
│                                                             │
│         ┌───────────────────────────────────────┐          │
│         │  Ask anything... "fix the bug in..."  │          │
│         │                                       │          │
│         │  code  ·  claude-sonnet-4-6           │          │
│         └───────────────────────────────────────┘          │
│                                                             │
│              tab  modes     ctrl+p  commands                │
│                                                             │
│                                                             │
│         *  Tip  Ketik /connect untuk setup provider        │
│                                                             │
│                                              v0.1.0         │
└─────────────────────────────────────────────────────────────┘
```

### Spesifikasi Splash Screen

```
Logo "multacd"  : ASCII art besar, warna Lavender (#b4befe)
                  atau bisa plain text besar dengan spacing
Input box       : Terpusat, lebar ~60% layar
                  Placeholder teks redup (Overlay 0)
                  Border tipis warna Surface 2
Info bawah input: mode aktif · nama model
                  warna Subtext 0 (redup)
Shortcut hints  : "tab  modes   ctrl+p  commands"
                  warna Overlay 1
Tip             : muncul bergantian kalau banyak tips
                  bullet dengan warna Peach (#fab387)
Versi           : pojok kanan bawah, Overlay 1

Transisi        : Saat user mulai ketik → splash hilang
                  → masuk ke layout normal (chat panel)
                  Animasi: fade atau langsung, tidak perlu mewah
```

---

## 11. Info Panel Kanan (Context Panel)

Panel kanan yang tampil di semua mode (bisa di-toggle).
Terinspirasi dari panel kanan OpenCode yang tampilkan context info.

```
┌──────────────────────────────────┬───────────────────────┐
│                                  │  Go CLI for IndexNow  │  ← judul project
│   [Chat Panel]                   │  ─────────────────    │
│                                  │  Context              │
│                                  │  12,450 tokens        │
│                                  │  18% used             │
│                                  │  $0.003 spent         │
│                                  │  ─────────────────    │
│                                  │  Session              │
│                                  │  Started: 14:32       │
│                                  │  Messages: 12         │
│                                  │  Tools run: 8         │
│                                  │  ─────────────────    │
│                                  │  Model                │
│                                  │  claude-sonnet-4-6    │
│                                  │  Anthropic            │
└──────────────────────────────────┴───────────────────────┘

Toggle: Ctrl+I (info panel)
Posisi: Kanan
Width : ~25% layar
```

### Isi Info Panel per Mode

```
Mode /code:
  Project name (dari scan codebase)
  Context (tokens, %, cost)
  Session (waktu mulai, jumlah pesan, tools run)
  Model (nama, provider)
  Git (branch, last commit)

Mode /research:
  Topik research (kalau sedang running)
  Context (tokens, %, cost)
  Round progress (untuk deep research)
  Sources: X read, Y failed
  Model

Mode /personal:
  Daemon status
  Bot status
  Users aktif
  Jobs scheduled
```

---

## 12. Model Selector Popup

Muncul saat user ketik `/model` atau tekan shortcut.
Terinspirasi dari model selector OpenCode — searchable, grouped, bisa favorite.

```
┌──────────────────────────────────────────────────┐
│  Select model                               esc  │
│  ──────────────────────────────────────────────  │
│  Search...                                       │
│  ──────────────────────────────────────────────  │
│                                                  │
│  Recent                                          │
│  * claude-sonnet-4-6  Anthropic                  │  ← selected (highlight)
│                                                  │
│  Anthropic                                       │
│    claude-haiku-4-5                              │
│    claude-sonnet-4-6                             │
│    claude-opus-4                                 │
│                                                  │
│  OpenAI                                          │
│    gpt-4o                                        │
│    gpt-4o-mini                                   │
│    o3                                            │
│                                                  │
│  Google                                          │
│    gemini-2.0-flash                              │
│    gemini-2.5-pro                                │
│                                                  │
│  Groq                                            │
│    llama-3.3-70b-versatile         Free          │
│    llama-3.1-8b-instant            Free          │
│                                                  │
│  Ollama (local)                                  │
│    llama3.2                        Local         │
│    qwen2.5-coder                   Local         │
│                                                  │
│  ctrl+a connect provider    ctrl+f favorite      │
└──────────────────────────────────────────────────┘
```

### Spesifikasi Model Selector

```
Posisi      : Overlay di tengah layar, width ~55%
Search      : Filter real-time saat user ketik
Navigasi    : Arrow Up/Down, Enter pilih, Esc tutup
Grouping    : Per provider, header provider warna Mauve
Selected    : Background Surface 1, bullet *
Recent      : Model yang terakhir dipakai, di atas
Free tag    : Label "Free" warna Green, untuk provider gratis
Local tag   : Label "Local" warna Teal, untuk Ollama/lokal
Favorite    : ctrl+f → tandai model, muncul di section "Favorites"
Connect     : ctrl+a → buka setup wizard untuk tambah provider baru

Model list  : Diambil dari LiteLLM provider list + Ollama local
              Difilter berdasarkan provider yang sudah dikonfigurasi di config.yaml
```

---

## 13. Permission Bar (Inline, Bukan Popup)

Menggantikan desain lama di Section 4.
Terinspirasi dari permission bar OpenCode — inline di bawah, tidak interrupt chat.

```
Tampilan normal (idle):
┌─────────────────────────────────────────────────────────────┐
│  thinking.......                                            │
├─────────────────────────────────────────────────────────────┤
│  > _                                                        │
└─────────────────────────────────────────────────────────────┘

Tampilan saat ada permission request:
┌─────────────────────────────────────────────────────────────┐
│  write_file  src/utils/helper.py                            │
│  Allow once    Allow always    Reject                       │
│  ctrl+f fullscreen    enter confirm                         │
├─────────────────────────────────────────────────────────────┤
│  > _   (disabled saat permission pending)                   │
└─────────────────────────────────────────────────────────────┘

Untuk operasi berisiko tinggi (delete, push ke main):
┌─────────────────────────────────────────────────────────────┐
│  ! delete_file  src/critical.py   permanent action          │
│  Allow once    Reject                                       │
│  (Allow always tidak tersedia untuk operasi ini)            │
├─────────────────────────────────────────────────────────────┤
│  > _                                                        │
└─────────────────────────────────────────────────────────────┘
```

### Spesifikasi Permission Bar

```
Tinggi      : 3 baris (nama tool + path, tombol pilihan, hint navigasi)
Background  : Surface 0 (#313244)
Border atas : Surface 2 (#585b70), tipis

Baris 1     : nama tool (Sapphire) + path/target (Subtext 1)
              kalau berisiko: tambah "!" di depan, warna Red
Baris 2     : "Allow once   Allow always   Reject"
              item yang sedang di-highlight → warna Text + underline
              kalau operasi berisiko: hapus "Allow always"
Baris 3     : hint navigasi kecil, warna Overlay 1

Navigasi    : Arrow Left/Right → pindah pilihan
              Enter → konfirmasi pilihan yang di-highlight
              Y → shortcut Allow once
              A → shortcut Allow always
              N / Escape → Reject

Input bar   : Di-disable (redup) saat permission pending
              Kembali aktif setelah user pilih
```

---

## Update Ringkasan — Semua Keputusan Desain

```
Section  Keputusan                      Mulai berlaku
───────  ──────────────────────────────  ─────────────
1        Icon system (Nerd Fonts)        Phase 2 TUI
2        Catppuccin theme                Phase 2 TUI
3        Layout (file tree kanan)        Phase 2 TUI
4        [DIGANTIKAN oleh Section 13]    -
5        Expandable tool activity        Phase 2 TUI
6        Thinking indicator              Phase 2 TUI
7        Slash command palette           Phase 2 TUI
8        Setup wizard                    Phase 2
9        Instalasi curl/irm              Phase 5
10       Splash screen                   Phase 2 TUI
11       Info panel kanan (Ctrl+I)       Phase 2 TUI
12       Model selector popup            Phase 2 TUI
13       Permission bar (inline, 3 brs)  Phase 2 TUI (ganti Section 4)

---

## 14. Redesign v2 (full bebas, Termux baseline v0.119)

Breaking visual, kompatibel config (config v1 tetap kebaca):

- Tema default = multacd-dark (identitas sendiri, turunan Mocha dengan
  aksen sapphire + kontras naik buat HP). Catppuccin 4 varian tetap ada.
  Tambah multacd-light + multacd-min (16 warna sistem, Termux hemat).
  Token semantik di tui/tokens.py — widget dilarang hardcode hex.
- Icon unicode tanpa emoji 2-cell. Auto jadi ascii kalau
  NO_EMOJI/NO_COLOR/Termux sempit (<70 kolom).
- Status bar responsif: <70 kolom tampil 'multacd - mode - status' saja.
  Bukan repo = segmen git hilang (bukan 'no git').
- Thinking statis saat MULTACD_MIN=1/NO_COLOR (tanpa repaint 200ms).
- Slash palette fuzzy berperingkat: '/md' ketemu '/model'.
- Tool header berwarna (run biru/sukses hijau/gagal merah).
- Splash v2: logo + mode-model-versi + 1 tip. Welcome ringkas 2 baris.
- Panel kanan min-width 28 ke 20. Git watcher 60 dtk saat min-mode.
- AskDialog responsif (80% max 60) + ikon tanpa emoji.
- Wizard numbering /6 (sebelumnya campur /5 dan /6).
- File tree marker peach #fab387.
