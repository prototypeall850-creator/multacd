# multacd — PLAN.md
> Agentic TUI: Coding Agent + Research Agent + Personal Agent
> Stack: Python · Textual · LiteLLM (BYOK)
> Vibe coding — kamu yang build, plan ini panduan arahnya

---

## Daftar Isi

1. [Visi & Scope](#1-visi--scope)
2. [Target Platform](#2-target-platform)
3. [Tech Stack](#3-tech-stack)
4. [Struktur Folder](#4-struktur-folder)
5. [Sistem Config (BYOK)](#5-sistem-config-byok)
6. [Sistem Permission Tool](#6-sistem-permission-tool)
7. [Agent Loop](#7-agent-loop)
8. [TUI Layout](#8-tui-layout)
9. [Step-by-Step Build Phase 1](#9-step-by-step-build-phase-1)
10. [Deliverable Phase 1](#10-deliverable-phase-1)
11. [Roadmap Phase Selanjutnya](#11-roadmap-phase-selanjutnya)

---

## 1. Visi & Scope

```
multacd
│
├── Mode 1: 💻 Coding Agent    → seperti Claude Code / OpenCode
├── Mode 2: 🔍 Research Agent  → seperti Perplexity, deep web search
└── Mode 3: 📱 Personal Agent  → integrasi Telegram & WhatsApp
```

Satu TUI, tiga mode, satu config BYOK.
Phase 1 fokus membangun **pondasi** yang ketiga mode ini akan berdiri di atasnya.

---

## 2. Target Platform

| Platform | Dukungan | Catatan |
|---|---|---|
| Linux | ✅ Full | Native, paling mulus |
| macOS | ✅ Full | Native, no issue |
| Windows | ✅ Full | Wajib pakai Windows Terminal |
| Android (Termux) | ✅ Full | `pkg install python git` dulu |

Satu codebase jalan di semua platform — ini dicapai lewat:
- `pathlib` untuk semua operasi path (bukan string path manual)
- Deteksi OS otomatis untuk shell (`bash` vs `powershell`)
- Tidak ada dependency yang Termux tidak support di Phase 1

---

## 3. Tech Stack

### Core Dependencies

| Library | Fungsi | Alasan Dipilih |
|---|---|---|
| `textual` | TUI framework | Paling modern, aktif dikembangkan, support mouse & warna |
| `rich` | Rendering teks & syntax highlight | Sudah bundled bersama Textual |
| `litellm` | BYOK — semua LLM provider | 1 interface untuk 100+ provider |
| `pyyaml` | Baca/tulis config.yaml | Format YAML paling mudah dibaca manusia |
| `pydantic` | Validasi config & tool params | Catch error config sebelum crash |
| `httpx` | HTTP requests async | Lebih modern dari `requests`, support async |
| `sqlite3` | Long-term memory | Built-in Python, zero install |
| `pathlib` | Cross-platform file path | Built-in Python |

### File requirements.txt

```
textual>=0.80.0
litellm>=1.40.0
pyyaml>=6.0
pydantic>=2.0
httpx>=0.27.0
```

> `rich`, `sqlite3`, `pathlib` tidak perlu masuk requirements.txt
> karena sudah built-in atau bundled.

---

## 4. Struktur Folder

```
multacd/
│
├── main.py                      ← entry point: python main.py
├── requirements.txt             ← semua pip dependencies
├── PLAN.md                      ← dokumen ini
├── README.md                    ← cara install & pakai
│
├── core/                        ← jantung project
│   ├── __init__.py
│   ├── config.py                ← baca & validasi ~/.multacd/config.yaml
│   ├── llm_client.py            ← wrapper LiteLLM, handle streaming & tool call
│   ├── agent_loop.py            ← ReAct loop utama
│   └── permissions.py           ← logic auto-approved vs ask vs deny
│
├── tools/                       ← semua tool yang bisa dipakai agent
│   ├── __init__.py
│   ├── registry.py              ← daftar & routing semua tool
│   │
│   ├── filesystem/
│   │   ├── __init__.py
│   │   ├── read_file.py
│   │   ├── read_many_files.py
│   │   ├── write_file.py
│   │   ├── edit_file.py
│   │   ├── multi_edit.py
│   │   ├── apply_patch.py
│   │   ├── move_file.py
│   │   ├── delete_file.py
│   │   ├── glob.py
│   │   ├── grep.py
│   │   └── list_dir.py
│   │
│   ├── shell/
│   │   ├── __init__.py
│   │   └── bash.py              ← auto-detect OS: bash / powershell
│   │
│   ├── git/
│   │   ├── __init__.py
│   │   ├── git_status.py
│   │   ├── git_diff.py
│   │   ├── git_log.py
│   │   ├── git_add.py
│   │   ├── git_commit.py
│   │   ├── git_push.py
│   │   ├── git_pull.py
│   │   ├── git_branch.py
│   │   └── git_checkout.py
│   │
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── remember.py
│   │   ├── recall.py
│   │   └── forget.py
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── task.py              ← spawn subtask ke agent
│   │   ├── skill.py             ← simpan & load skill
│   │   ├── ask.py               ← minta konfirmasi ke user
│   │   └── todo_write.py        ← tulis & update todo list agent
│   │
│   └── web/
│       ├── __init__.py
│       └── web_fetch.py         ← fetch konten URL (perlu konfirmasi)
│
├── tui/                         ← semua yang tampil di terminal
│   ├── __init__.py
│   ├── app.py                   ← Textual App, entry TUI
│   ├── screens/
│   │   ├── __init__.py
│   │   └── main_screen.py       ← layout layar utama
│   └── widgets/
│       ├── __init__.py
│       ├── chat_panel.py        ← panel percakapan (scrollable)
│       ├── input_bar.py         ← input box bawah layar
│       ├── status_bar.py        ← info model aktif, mode, status agent
│       └── confirm_dialog.py    ← popup saat tool butuh konfirmasi
│
└── memory/
    ├── __init__.py
    ├── context.py               ← short-term: history pesan dalam sesi
    └── store.py                 ← long-term: SQLite (remember/recall/forget)
```

---

## 5. Sistem Config (BYOK)

### Lokasi Config

```
~/.multacd/
├── config.yaml      ← config utama (dibuat user)
├── memory.db        ← SQLite long-term memory
└── skills/          ← folder skill yang disimpan agent
    └── *.md
```

> Semua data multacd tersimpan di home directory user.
> Folder project (repo) tidak menyimpan data personal apapun.

### Saat Pertama Kali Jalan

```
Kalau ~/.multacd/config.yaml belum ada:
  → multacd cetak pesan setup
  → tunjukkan contoh config lengkap
  → minta user buat file tersebut
  → exit dengan instruksi yang jelas
```

### Isi config.yaml

```yaml
# ~/.multacd/config.yaml

# ── Model (wajib diisi) ──────────────────────────────
model: "anthropic/claude-sonnet-4-6"
api_key: "sk-ant-xxxx"

# Contoh provider lain (uncomment salah satu):
#
# OpenAI
# model: "openai/gpt-4o"
# api_key: "sk-xxxx"
#
# Google Gemini
# model: "gemini/gemini-2.0-flash"
# api_key: "AIzaxxxx"
#
# Groq (cepat & murah)
# model: "groq/llama-3.3-70b-versatile"
# api_key: "gsk_xxxx"
#
# Ollama (lokal, gratis)
# model: "ollama/llama3.2"
# api_base: "http://localhost:11434"
# api_key: "none"
#
# Custom OpenAI-compatible endpoint
# model: "openai/nama-model"
# api_base: "https://endpoint-kamu.com/v1"
# api_key: "key-kamu"

# ── Agent Settings ───────────────────────────────────
max_tokens: 8096
temperature: 0.3
max_tool_iterations: 20      # batas loop per task, hindari infinite loop

# ── Permission Settings ──────────────────────────────
auto_approve_reads: true     # semua tool READ → langsung jalan
ask_before_write: true       # semua tool WRITE → konfirmasi dulu
ask_before_bash: true        # bash → konfirmasi dulu
ask_before_web: true         # web_fetch → konfirmasi dulu

# ── Display Settings ─────────────────────────────────
theme: "dark"                # dark | light
show_tool_calls: true        # tampilkan nama tool yang dijalankan
show_thinking: false         # tampilkan reasoning LLM (verbose mode)
```

---

## 6. Sistem Permission Tool

### Kategori Permission

#### AUTO-APPROVED — Langsung jalan tanpa tanya

```
FILESYSTEM READ (tidak mengubah apapun):
  read_file          baca isi satu file
  read_many_files    baca beberapa file sekaligus
  glob               cari file by pattern (*.py, src/**)
  grep               cari string/pattern dalam file
  list_dir           lihat isi folder

META-AGENT (tidak menyentuh filesystem):
  task               buat subtask baru
  ask                minta input/konfirmasi ke user
  skill              load atau simpan skill
  todo_write         tulis & update todo list agent
  remember           simpan ke long-term memory
  recall             baca dari long-term memory
  forget             hapus dari long-term memory

GIT (semua operasi git):
  git_status         lihat status repo
  git_diff           lihat perubahan belum di-commit
  git_log            lihat history commit
  git_branch         lihat daftar branch
  git_add            stage file ke index
  git_commit         commit perubahan
  git_push           push ke remote
  git_pull           pull dari remote
  git_checkout       ganti atau buat branch
```

#### ASK BY DEFAULT — Muncul konfirmasi dulu sebelum jalan

```
FILESYSTEM WRITE (bisa merusak atau mengubah file):
  write_file         tulis atau buat file baru
  edit_file          edit bagian isi file
  multi_edit         edit banyak file sekaligus
  apply_patch        terapkan diff/patch ke file
  move_file          pindah atau rename file
  delete_file        hapus file ⚠️ tidak bisa di-undo

SHELL:
  bash               jalankan perintah shell ⚠️ bisa apa saja

WEB:
  web_fetch          akses & fetch konten dari URL
```

### Alur Konfirmasi (ASK)

```
Agent hendak jalankan: write_file
            │
            ▼
┌───────────────────────────────────┐
│  ⚠️  Konfirmasi Diperlukan        │
│                                   │
│  Tool   : write_file              │
│  Target : src/utils/helper.py     │
│  Aksi   : Buat file baru          │
│                                   │
│  [Y] Izinkan    [N] Tolak         │
│  [A] Izinkan Semua Sesi Ini       │
└───────────────────────────────────┘
            │
     ┌──────┴──────┐
    [Y]           [N]
     │             │
     ▼             ▼
  Jalankan    Beritahu LLM
  tool        dibatalkan,
              LLM cari cara lain
```

> Opsi **[A] Izinkan Semua** hanya berlaku untuk sesi ini.
> Sesi berikutnya kembali ke default ask.

---

## 7. Agent Loop

### ReAct Pattern (Reason → Act → Observe)

```
User kirim input
       │
       ▼
Tambah ke messages history
  { role: "user", content: "..." }
       │
       ▼
Kirim seluruh history ke LLM
  via LiteLLM (streaming)
       │
       ▼
Parse response LLM
       │
  ┌────┴────┐
TEXT      TOOL CALL
  │           │
  ▼           ▼
Stream     Ambil nama tool
teks ke    & parameternya
TUI            │
  │            ▼
  │       Cek permission
  │            │
  │    ┌───────┴────────┐
  │  AUTO             ASK
  │    │               │
  │    ▼               ▼
  │  Langsung    Tampilkan
  │  jalankan    confirm dialog
  │    │               │
  │    │         ┌─────┴──────┐
  │    │        [Y]          [N]
  │    │         │            │
  │    │         ▼            ▼
  │    │       Jalankan   Tambah ke
  │    │       tool       history:
  │    │         │        "Dibatalkan
  │    │         │         user"
  │    └────┬────┘
  │         │
  │         ▼
  │    Tambah hasil tool ke history
  │    { role: "tool", content: hasil }
  │         │
  │         ▼
  │    Loop kembali ke LLM
  │    (LLM baca hasil, mikir lagi)
  │         │
  │    (sampai LLM tidak ada
  │     tool call lagi)
  │         │
  └────┬────┘
       │
       ▼
Tunggu input user berikutnya
```

### Batas Keamanan Agent Loop

```python
# Di agent_loop.py — hardcoded safety limit
MAX_ITERATIONS = config.max_tool_iterations  # default: 20

iteration = 0
while True:
    iteration += 1
    if iteration > MAX_ITERATIONS:
        # Hentikan loop, beritahu user
        break
    # ... lanjut loop
```

---

## 8. TUI Layout

```
┌─────────────────────────────────────────────────────────┐
│  ⚡ multacd  ·  💻 coding  ·  claude-sonnet-4-6  ·  ●  │  ← Status Bar
├─────────────────────────────────────────────────────────┤
│                                                         │
│                                                         │
│  ┌─ You ──────────────────────────────────────────────┐ │
│  │  buatin file hello.py yang print hello world       │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ multacd ──────────────────────────────────────────┐ │
│  │  Oke, langsung gua buatin.                         │ │
│  │                                                    │ │
│  │  🔧 write_file · hello.py ··················· ✅  │ │
│  │                                                    │ │
│  │  Udah jadi! Isinya:                                │ │
│  │  ╔══════════════════════════════╗                  │ │
│  │  ║ print("Hello, World!")       ║                  │ │
│  │  ╚══════════════════════════════╝                  │ │
│  │                                                    │ │
│  │  Mau langsung dijalanin?                           │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  ❯ _                                      Ctrl+C quit  │  ← Input Bar
└─────────────────────────────────────────────────────────┘
```

### Komponen TUI

| Widget | File | Fungsi |
|---|---|---|
| Status Bar | `status_bar.py` | Nama app, mode aktif, model, status agent (idle/thinking) |
| Chat Panel | `chat_panel.py` | Tampilkan percakapan, scrollable, render markdown |
| Input Bar | `input_bar.py` | Input multi-line, submit dengan Enter |
| Confirm Dialog | `confirm_dialog.py` | Popup Y/N saat tool butuh konfirmasi |

---

## 9. Step-by-Step Build Phase 1

> Urutan ini penting — setiap step bergantung pada step sebelumnya.
> Jangan skip, jangan loncat.

---

### Step 1 — Setup Project & Environment

**Tujuan:** Fondasi project siap, dependency terinstall.

```
Tugas:
  [ ] Buat folder: multacd/
  [ ] Masuk ke folder: cd multacd
  [ ] Init git repo: git init
  [ ] Buat virtual environment: python -m venv .venv
  [ ] Aktifkan venv:
        Linux/macOS/Termux : source .venv/bin/activate
        Windows            : .venv\Scripts\activate
  [ ] Buat requirements.txt (isi seperti di Section 3)
  [ ] Install semua: pip install -r requirements.txt
  [ ] Buat semua folder & file __init__.py kosong
      (sesuai struktur di Section 4)
  [ ] Buat .gitignore (minimal: .venv/, *.pyc, __pycache__)

Hasil: Folder project siap, semua library terinstall.
```

---

### Step 2 — Config System

**Tujuan:** multacd bisa baca BYOK config dari `~/.multacd/config.yaml`.

```
Tugas:
  [ ] Buat folder ~/.multacd/ kalau belum ada
  [ ] Buat core/config.py:
        - Definisikan model Config dengan Pydantic
          (field: model, api_key, api_base, max_tokens,
           temperature, max_tool_iterations, permissions, display)
        - Fungsi load_config() → baca ~/.multacd/config.yaml
        - Kalau file tidak ada → cetak pesan setup + contoh config
        - Kalau field wajib kosong → cetak error yang jelas
  [ ] Test: jalankan config.py, pastikan bisa baca YAML

Hasil: Config bisa diload, error ditangani dengan pesan jelas.
```

---

### Step 3 — LLM Client

**Tujuan:** multacd bisa kirim pesan ke LLM provider manapun.

```
Tugas:
  [ ] Buat core/llm_client.py:
        - Fungsi setup_client(config) → init LiteLLM dengan config
        - Fungsi stream_completion(messages, tools) → kirim ke LLM
          dengan streaming (teks muncul real-time, tidak nunggu selesai)
        - Fungsi parse_response(response) → pisahkan:
            · text content → untuk ditampilkan ke user
            · tool_calls   → untuk diproses agent loop
        - Error handling:
            · API key salah     → pesan jelas
            · Model tidak ada   → pesan jelas
            · Koneksi gagal     → retry 3x lalu error
            · Rate limit        → tunggu lalu retry
  [ ] Test: kirim "hello" ke LLM, pastikan dapat respons

Hasil: Bisa ngobrol ke LLM, streaming jalan, error ditangani.
```

---

### Step 4 — Permission System

**Tujuan:** Sistem tahu tool mana yang langsung jalan dan mana yang harus tanya dulu.

```
Tugas:
  [ ] Buat core/permissions.py:
        - Definisikan dua set tool (AUTO_APPROVED & ASK_REQUIRED)
          persis seperti di Section 6
        - Fungsi check_permission(tool_name) → return:
            "auto"  → langsung jalankan
            "ask"   → minta konfirmasi dulu
            "deny"  → tidak diizinkan sama sekali
        - Support override dari config
          (kalau user set auto_approve_reads: false,
           tool read pun harus ask)
  [ ] Test: panggil check_permission() untuk beberapa tool,
      pastikan hasilnya benar

Hasil: Sistem permission jalan, siap dipakai agent loop.
```

---

### Step 5 — Tool System

**Tujuan:** Semua tool yang agent bisa pakai sudah tersedia.

```
Tugas:
  [ ] Buat format return yang konsisten untuk semua tool:
        {
          "success": true/false,
          "result": "...",    ← isi kalau sukses
          "error": "..."      ← isi kalau gagal
        }

  [ ] Implement tool AUTO-APPROVED dulu:
        read_file          baca isi file, return sebagai string
        read_many_files    baca beberapa file, return dict
        glob               cari file by pattern
        grep               cari string dalam file atau folder
        list_dir           list isi folder + info file
        remember           simpan key-value ke SQLite
        recall             baca dari SQLite
        forget             hapus dari SQLite
        task               (placeholder dulu, Phase 2 implementasi penuh)
        ask                tampilkan pertanyaan ke user, tunggu jawaban
        skill              simpan/load file .md di ~/.multacd/skills/
        todo_write         tulis file todo.md di working directory

  [ ] Implement tool ASK-REQUIRED:
        write_file         tulis konten ke file (buat baru atau overwrite)
        edit_file          edit bagian spesifik file (cari & ganti)
        multi_edit         kumpulan edit_file dalam satu call
        apply_patch        terapkan unified diff ke file
        move_file          pindah atau rename file
        delete_file        hapus file (minta konfirmasi extra)
        bash               jalankan shell command
                           (auto-detect: bash di Linux/macOS/Termux,
                            powershell di Windows)
        web_fetch          fetch konten URL, return sebagai teks

  [ ] Buat tools/registry.py:
        - Dict semua tool: { "nama_tool": fungsi_tool }
        - Fungsi get_tool_definitions() → return daftar tool
          dalam format yang LLM mengerti (JSON Schema)
        - Fungsi execute_tool(name, params) → jalankan tool

Hasil: Semua tool tersedia, bisa dipanggil dengan nama.
```

---

### Step 6 — Memory System

**Tujuan:** Agent punya ingatan — baik dalam sesi maupun antar sesi.

```
Tugas:
  [ ] Buat memory/context.py (short-term):
        - Class ConversationContext
        - Simpan messages sebagai list Python biasa
        - Fungsi add_message(role, content)
        - Fungsi add_tool_result(tool_name, result)
        - Fungsi get_messages() → return semua messages
        - Fungsi clear() → kosongkan history (mulai sesi baru)

  [ ] Buat memory/store.py (long-term):
        - Inisialisasi SQLite di ~/.multacd/memory.db
        - Buat tabel: key (TEXT PRIMARY KEY), value (TEXT), timestamp
        - Fungsi remember(key, value) → simpan atau update
        - Fungsi recall(key) → baca nilai
        - Fungsi recall_all() → baca semua
        - Fungsi forget(key) → hapus

Hasil: Agent bisa ingat sesuatu dalam sesi & antar sesi.
```

---

### Step 7 — Agent Loop

**Tujuan:** Sambungkan LLM + tools + memory menjadi loop yang berjalan.

```
Tugas:
  [ ] Buat core/agent_loop.py:
        - Fungsi run(user_input, context, config):
            1. Tambah user_input ke context
            2. Ambil tool definitions dari registry
            3. Kirim messages + tools ke LLM (streaming)
            4. Parse response:
               a. Kalau TEXT → stream ke TUI
               b. Kalau TOOL CALL → proses tool
            5. Proses tool:
               a. Cek permission (auto / ask)
               b. Kalau ask → yield event "needs_confirmation"
                  → tunggu jawaban user dari TUI
               c. Kalau diizinkan → execute_tool()
               d. Tambah hasil ke context
               e. Loop kembali ke step 3
            6. Berhenti kalau tidak ada tool call lagi
               atau sudah capai max_tool_iterations

  [ ] Implementasikan sebagai async generator:
        → setiap update (teks baru, tool call, dll)
          di-yield ke TUI secara real-time

Hasil: Agent bisa "mikir" dan "ngerjain" sesuatu secara otomatis.
```

---

### Step 8 — TUI

**Tujuan:** Semua yang terjadi bisa dilihat dan dikontrol dari terminal.

```
Tugas:
  [ ] Buat tui/widgets/status_bar.py:
        - Tampilkan: nama app · mode · nama model · status (idle/thinking)
        - Update status otomatis saat agent sedang berjalan

  [ ] Buat tui/widgets/chat_panel.py:
        - Panel scrollable untuk percakapan
        - Render pesan user (rata kanan atau beda warna)
        - Render pesan agent + streaming real-time
        - Render tool call: [🔧 nama_tool] ··· ✅ atau ❌
        - Render markdown (bold, code block, list)

  [ ] Buat tui/widgets/input_bar.py:
        - Input box di bagian bawah
        - Enter → kirim pesan
        - Shift+Enter → newline (multi-line input)
        - Disable saat agent sedang berpikir

  [ ] Buat tui/widgets/confirm_dialog.py:
        - Popup di tengah layar
        - Tampilkan: nama tool, target file/command, aksi
        - Tombol: [Y] Izinkan · [N] Tolak · [A] Izinkan Semua

  [ ] Buat tui/screens/main_screen.py:
        - Susun semua widget: status_bar + chat_panel + input_bar
        - Handle event dari agent_loop (update chat, minta konfirmasi)

  [ ] Buat tui/app.py:
        - Textual App utama
        - Load config saat startup
        - Kalau config tidak ada → tampilkan pesan setup, exit
        - Sambungkan TUI ke agent_loop

Hasil: TUI interaktif, streaming real-time, konfirmasi tool jalan.
```

---

### Step 9 — Entry Point & Polish

**Tujuan:** `python main.py` langsung jalan dengan experience yang baik.

```
Tugas:
  [ ] Buat main.py:
        - Baca argumen CLI kalau ada (--config, --model, dll)
        - Jalankan TUI app

  [ ] Pesan welcome saat pertama buka:
        - Tampilkan nama app + versi
        - Tampilkan model yang sedang dipakai
        - Hint shortcut penting (Ctrl+C untuk keluar, dll)

  [ ] Error messages yang friendly:
        - Jangan tampilkan Python traceback mentah ke user
        - Tangkap semua exception, tampilkan pesan yang bisa dimengerti

  [ ] Handle Ctrl+C dengan graceful:
        - Kalau agent sedang jalan → stop agent dulu
        - Tanya konfirmasi sebelum keluar
        - Baru exit

  [ ] Tulis README.md:
        - Cara install (Linux, macOS, Windows, Termux)
        - Cara setup config.yaml
        - Cara jalankan
        - Daftar shortcut TUI

Hasil: multacd siap dipakai, experience bersih dari awal sampai akhir.
```

---

## 10. Deliverable Phase 1

Setelah semua step selesai, multacd harus bisa melakukan ini:

```
Setup & Config
  ✅ Jalan dengan: python main.py
  ✅ Baca BYOK config dari ~/.multacd/config.yaml
  ✅ Kalau config belum ada → tampilkan instruksi setup yang jelas
  ✅ Support semua provider LLM via LiteLLM

Filesystem
  ✅ Baca file & folder (auto-approved, langsung jalan)
  ✅ Cari file by pattern (glob) dan by isi (grep)
  ✅ Tulis, edit, pindah, hapus file (minta konfirmasi dulu)

Shell
  ✅ Jalankan command bash/powershell (minta konfirmasi dulu)
  ✅ Deteksi OS otomatis: Linux/macOS/Termux → bash, Windows → powershell

Memory
  ✅ Ingat sesuatu dalam sesi (short-term)
  ✅ Simpan & recall antar sesi (long-term, SQLite)

TUI
  ✅ Tampilan interaktif di terminal
  ✅ Streaming real-time (teks muncul saat LLM generate, tidak nunggu selesai)
  ✅ Popup konfirmasi saat tool perlu izin
  ✅ Jalan mulus di Linux, macOS, Windows, Termux
```

---

## 11. Roadmap Phase Selanjutnya

```
Phase 2 — Coding Agent
  → Git tools lengkap (sudah ada di Phase 1, diperdalam)
  → Codebase awareness: baca & pahami seluruh struktur project
  → Jalankan & test kode (python, node, dll)
  → Linting & auto-fix
  → Mode /code sebagai default mode

Phase 3 — Research Agent
  → Integrasi web search API (Brave Search / SerpAPI)
  → Web scraping: httpx + BeautifulSoup
  → Deep research mode: multi-step, banyak sumber, cross-reference
  → Synthesize & summarize ala Perplexity
  → Mode /research

Phase 4 — Personal Agent
  → Telegram bot gateway
  → WhatsApp gateway
  → Background scheduler (cron jobs)
  → Briefing harian otomatis
  → Mode /personal, bisa dikontrol dari HP
```

---

*multacd PLAN.md · Phase 1*
*Ini panduan arah, bukan hukum. Boleh disesuaikan saat build.*
