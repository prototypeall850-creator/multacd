# multacd — PLAN Phase 2: Coding Agent
> Dibangun di atas Phase 1 yang sudah selesai
> Stack: Python · Textual · LiteLLM · ruff · pytest

---

## Daftar Isi

1. [Tujuan Phase 2](#1-tujuan-phase-2)
2. [Yang Berubah dari Phase 1](#2-yang-berubah-dari-phase-1)
3. [Tambahan Struktur Folder](#3-tambahan-struktur-folder)
4. [soul.md System](#4-soulmd-system)
5. [Codebase Awareness](#5-codebase-awareness)
6. [Mode Switching](#6-mode-switching)
7. [Code Execution](#7-code-execution)
8. [Code Quality Tools](#8-code-quality-tools)
9. [Smart Git Flow](#9-smart-git-flow)
10. [System Prompt Composition](#10-system-prompt-composition)
11. [TUI Enhancement](#11-tui-enhancement)
12. [Step-by-Step Build Phase 2](#12-step-by-step-build-phase-2)
13. [Deliverable Phase 2](#13-deliverable-phase-2)

---

## 1. Tujuan Phase 2

Phase 1 membangun pondasi — agent bisa ngobrol, jalankan tool, dan tampil di TUI.

Phase 2 mengubah multacd dari **tool generik** menjadi **coding partner yang ngerti konteks:**

```
Phase 1: "Jalankan tool ini"
Phase 2: "Gua udah baca codebase kamu, ngerti structurenya,
           bisa run, lint, test, dan handle git dengan cerdas"
```

---

## 2. Yang Berubah dari Phase 1

### Ditambah (baru)
```
soul.md system          → agent punya kepribadian
Codebase Awareness      → auto-scan project saat startup
Mode Switching          → /code /research /personal /clear /model
Code Execution          → run_python tool
Code Quality            → lint_python, run_tests tools
Smart Git Flow          → enhanced dari git tools Phase 1
System Prompt Composer  → gabungkan soul + context + mode
TUI: file tree panel    → toggle Ctrl+T
TUI: diff viewer        → tampilkan git diff dengan highlight
TUI: git status bar     → branch + changed files di status bar
```

### Diupdate (dari Phase 1)
```
core/agent_loop.py      → tambah mode awareness
core/permissions.py     → tambah tool baru ke daftar
tools/registry.py       → register tool baru
tools/git/*.py          → enhance dengan Smart Git Flow
tui/widgets/status_bar  → tambah info branch & mode
```

### Tidak Berubah
```
Semua tool Phase 1 tetap jalan seperti biasa.
Config system, LLM client, memory system — tidak ada perubahan.
```

---

## 3. Tambahan Struktur Folder

Hanya folder/file baru — tidak menggambarkan ulang Phase 1.

```
multacd/
│
├── core/
│   ├── codebase.py              ← BARU: codebase awareness engine
│   ├── mode_manager.py          ← BARU: handle mode switching
│   └── prompt_composer.py       ← BARU: susun system prompt
│
├── tools/
│   ├── code/                    ← BARU: semua tool eksekusi kode
│   │   ├── __init__.py
│   │   ├── run_python.py        ← jalankan file/snippet Python
│   │   ├── lint_python.py       ← lint dengan ruff
│   │   └── run_tests.py         ← jalankan pytest
│   │
│   └── codebase/                ← BARU: tool analisis codebase
│       ├── __init__.py
│       └── scan_codebase.py     ← scan struktur project
│
└── tui/
    └── widgets/
        ├── file_tree.py         ← BARU: panel file tree (toggle)
        └── diff_viewer.py       ← BARU: tampilkan git diff
```

### Dependency Tambahan Phase 2

```
# Tambahkan ke requirements.txt
ruff>=0.4.0          # linter Python yang cepat
pytest>=8.0.0        # test runner
gitpython>=3.1.0     # git operations (mungkin sudah ada)
```

---

## 4. soul.md System

### Konsep
soul.md adalah file kepribadian agent yang di-inject ke system prompt
di bagian paling awal setiap sesi. Ini yang bikin multacd punya
"karakter" konsisten di semua interaksi.

### Lokasi & Prioritas

```
Prioritas 1 (override): ~/.multacd/soul.md     ← punya user, custom
Prioritas 2 (default) : multacd/soul.md        ← bawaan project

Kalau ~/.multacd/soul.md ada → pakai itu
Kalau tidak ada → pakai soul.md dari folder project
```

### Cara Kerjanya

```
Saat startup:
  1. Cek apakah ~/.multacd/soul.md ada
  2. Kalau ada → load itu
  3. Kalau tidak → load soul.md dari root project
  4. Simpan konten sebagai string
  5. Inject ke system prompt (lihat Section 10)

Saat sesi berjalan:
  soul.md tidak di-reload — cukup sekali saat startup
  Kalau user edit soul.md → efeknya sesi berikutnya
```

### Implementasi di core/prompt_composer.py

```python
def load_soul(config_dir, project_dir):
    """
    Load soul.md dengan urutan prioritas:
    1. ~/.multacd/soul.md (user custom)
    2. {project_dir}/soul.md (default bawaan)
    3. Hardcoded minimal fallback kalau keduanya tidak ada
    """
```

---

## 5. Codebase Awareness

### Tujuan
Agent otomatis "ngerti" project yang sedang dibuka
tanpa user perlu jelasin dulu.

### Kapan Dijalankan
```
Saat startup → auto-scan working directory
User pindah project → bisa trigger ulang dengan /scan
```

### Apa yang Discan

```
SELALU DISCAN:
  Struktur folder (2-3 level depth, ignore hidden folders)
  File kunci di root:
    README.md              → deskripsi project
    .env.example           → variable environment yang dibutuhkan
    requirements.txt       → Python dependencies
    pyproject.toml         → config project Python modern
    setup.py / setup.cfg   → config project Python lama
    Makefile               → command shortcut project
    docker-compose.yml     → kalau ada Docker setup
    soul.md                → kepribadian agent (kalau ada custom)
  Entry point:
    main.py, app.py, run.py, index.py (di root)
  Git info:
    branch aktif
    status (clean / ada perubahan)
    remote URL (untuk tahu ini repo apa)

TIDAK DISCAN (skip):
  PLAN.md, ROADMAP.md      ← file planning, bukan kode
  .venv/, node_modules/    ← dependency folders
  __pycache__/, *.pyc      ← compiled files
  .git/                    ← git internals
  Semua yang ada di .gitignore
```

### Output yang Dihasilkan

```
Project Context (string yang diinjek ke system prompt):

"Project: myapp
Type: Python application
Entry point: main.py
Dependencies: textual, litellm, pyyaml, pydantic (dari requirements.txt)
Structure:
  core/         → agent logic (config.py, agent_loop.py, ...)
  tools/        → tool implementations
  tui/          → Textual TUI components
  memory/       → context & SQLite store
Git: branch 'main', 3 files modified
README: [ringkasan 2-3 kalimat dari README.md]"
```

### Deteksi Jenis Project

```
Ada requirements.txt atau pyproject.toml  → Python project
Ada package.json                          → Node.js project
Ada go.mod                                → Go project
Ada Cargo.toml                            → Rust project
Ada pom.xml                               → Java/Maven project
Tidak ada tanda-tanda spesifik            → Generic project
```

Deteksi ini dipakai untuk:
- Pilih tool yang relevan (run_python hanya muncul di Python project)
- Kasih context yang tepat ke LLM

### Implementasi

```
core/codebase.py:
  scan_project(root_path)          → return ProjectContext object
  detect_project_type(root_path)   → return string jenis project
  read_key_files(root_path)        → return dict {filename: content}
  build_file_tree(root_path)       → return string tree structure
  get_entry_points(root_path)      → return list file entry point

tools/codebase/scan_codebase.py:
  Tool yang bisa dipanggil agent manual kalau mau re-scan
  Berguna kalau user minta "baca dulu projectnya"
```

---

## 6. Mode Switching

### Daftar Mode

```
/code      → Coding Agent (default, aktif sejak startup)
/research  → Research Agent (placeholder — aktif di Phase 3)
/personal  → Personal Agent (placeholder — aktif di Phase 4)
```

### Daftar Command Lainnya

```
/clear          → clear conversation history, mulai sesi baru
/scan           → trigger ulang scan codebase
/model <nama>   → ganti model on-the-fly
                  contoh: /model openai/gpt-4o
/model          → (tanpa argumen) tampilkan model yang sedang aktif
/help           → tampilkan semua command yang tersedia
/soul           → tampilkan soul.md yang sedang aktif
```

### Cara Kerja Mode

```
User ketik /code → mode_manager.set_mode("code")
                 → update status bar
                 → update system prompt (mode-specific instructions)
                 → clear context? (tanya user dulu)

Tiap mode punya:
  - System prompt tambahan yang spesifik
  - Set tool yang diaktifkan
  - Warna/label berbeda di status bar
```

### Mode /code (aktif di Phase 2)

```
System prompt tambahan:
  "Kamu sedang dalam Coding Agent mode.
   Kamu punya akses ke: filesystem, shell, git, run_python,
   lint_python, run_tests.
   Fokus pada membantu user dengan kode dan development workflow."

Tools aktif: semua tool Phase 1 + tools baru Phase 2
Status bar : "💻 code" (warna hijau)
```

### Mode /research dan /personal (placeholder Phase 2)

```
Kalau user ketik /research atau /personal di Phase 2:
  → Tampilkan pesan: "Research Agent belum tersedia (coming Phase 3)"
  → Tetap di mode /code
```

### Implementasi

```
core/mode_manager.py:
  Class ModeManager
    set_mode(mode_name)          → ganti mode
    get_mode()                   → return mode aktif
    get_mode_prompt()            → return system prompt tambahan untuk mode ini
    get_active_tools()           → return list tool yang aktif di mode ini
    handle_command(input)        → parse / command dari input user
                                   return: (is_command, command, args)
```

---

## 7. Code Execution

### Tool: run_python

```
Nama    : run_python
Permission: ASK (butuh konfirmasi — ini jalankan kode!)

Input:
  file_path  : path ke file .py yang mau dijalankan (opsional)
  code       : snippet Python langsung (opsional)
               (salah satu dari keduanya harus diisi)
  args       : list argumen command line (opsional)
  timeout    : batas waktu dalam detik (default: 30)

Output:
  success    : true/false
  stdout     : output normal
  stderr     : output error
  exit_code  : 0 = sukses, non-zero = error
  duration   : berapa detik dijalankan

Contoh penggunaan agent:
  run_python(file_path="main.py")
  run_python(file_path="script.py", args=["--verbose", "--output", "out.txt"])
  run_python(code="print(2 + 2)")
```

### Fitur Penting run_python

```
1. Deteksi virtual environment otomatis:
   Cek apakah ada .venv/ di project → pakai python di .venv/bin/python
   Kalau tidak ada → pakai python dari PATH

2. Timeout protection:
   Kalau melebihi timeout → kill process, return error
   Pesan ke user: "Program dihentikan karena melebihi batas waktu X detik"

3. Streaming output:
   stdout dan stderr di-stream real-time ke TUI
   User bisa lihat output saat program masih jalan
   Tidak nunggu selesai dulu baru tampil

4. Kalau ada error (exit_code != 0):
   Agent otomatis baca traceback
   Analisis penyebab error
   Suggest fix — tapi tidak langsung auto-fix
   Tanya user dulu mau di-fix atau tidak
```

---

## 8. Code Quality Tools

### Tool: lint_python

```
Nama    : lint_python
Permission: AUTO (baca saja, tidak ubah file)
            KECUALI kalau fix=True → ASK

Input:
  path    : file atau folder yang mau di-lint
  fix     : true/false — kalau true, auto-fix yang bisa di-fix
            (default: false)

Output:
  success      : true/false
  issues       : list {file, line, column, code, message}
  fixed_count  : berapa yang berhasil di-fix (kalau fix=True)
  summary      : "X issues found in Y files"

Contoh penggunaan agent:
  lint_python(path="src/")
  lint_python(path="main.py", fix=True)
```

### Tool: run_tests

```
Nama    : run_tests
Permission: ASK (jalankan kode → perlu konfirmasi)

Input:
  path      : folder atau file test (default: "." — cari otomatis)
  test_name : nama test spesifik yang mau dijalankan (opsional)
  verbose   : true/false (default: false)

Output:
  success      : true/false
  passed       : jumlah test yang passed
  failed       : jumlah test yang failed
  errors       : jumlah test yang error (bukan failed, tapi error)
  skipped      : jumlah test yang skip
  duration     : total waktu jalankan semua test
  details      : list {name, status, message} per test yang gagal

Kalau ada yang failed:
  Agent baca detail error tiap test yang gagal
  Analisis penyebab
  Suggest fix — tidak auto-fix
  Tanya user mau dilanjut atau tidak
```

---

## 9. Smart Git Flow

### Enhancement dari Phase 1

Git tools di Phase 1 sudah ada tapi basic.
Phase 2 menambahkan **intelligence** di atas tool-tool itu.

### 9a. Auto Git Status saat Startup

```
Saat multacd dibuka di folder yang ada .git/:
  → Jalankan git_status otomatis (silent, tanpa minta konfirmasi)
  → Tampilkan hasilnya di status bar:
      "📍 main  ·  3 modified  ·  1 untracked"
  → Kalau ada perubahan besar → kasih tahu di chat area
    (bukan popup, cukup info di chat)

Kalau folder bukan git repo:
  → Status bar: "📍 no git"
  → Tidak ada git tools yang aktif
```

### 9b. LLM-Generated Commit Message

```
User: "commit semua perubahan ini"
  │
  ▼
Agent jalankan git_diff (AUTO — tidak perlu konfirmasi)
  │
  ▼
Agent baca diff, kirim ke LLM
  │
  ▼
LLM generate commit message dengan format Conventional Commits:
  feat: tambah codebase awareness di startup
  fix: perbaiki timeout pada run_python
  refactor: pisahkan mode_manager dari agent_loop
  docs: update README dengan instruksi setup baru
  chore: tambah ruff ke requirements.txt
  │
  ▼
Tampilkan ke user:
  ┌─────────────────────────────────────────┐
  │  📝 Commit Message (generated)          │
  │                                         │
  │  feat: tambah codebase awareness        │
  │                                         │
  │  [✓] Pakai ini   [✏️] Edit dulu         │
  └─────────────────────────────────────────┘
  │
  ▼
User approve atau edit → baru jalankan git_add + git_commit
```

### 9c. Diff Preview di TUI

```
Sebelum commit — tampilkan summary diff di diff_viewer:
  Files changed:
    M  core/agent_loop.py     (+45 / -12)
    A  core/codebase.py       (+230 / -0)
    M  requirements.txt       (+3 / -0)

User bisa review sebelum commit.
Diff viewer bisa di-toggle untuk lihat detail per file.
```

### 9d. Branch Protection

```
Kalau agent mau push ke branch bernama:
  main, master, production, prod, release, stable
    → Selalu tampilkan warning EXTRA sebelum push
    → Tampilkan konfirmasi berbeda dari ASK biasa:

  ┌─────────────────────────────────────────┐
  │  ⚠️  PERHATIAN — Branch Utama           │
  │                                         │
  │  Kamu akan push ke: main                │
  │  Commits: 3 commit baru                 │
  │                                         │
  │  Disarankan: buat branch baru dulu      │
  │                                         │
  │  [Push ke main]   [Buat branch baru]    │
  │  [Batal]                                │
  └─────────────────────────────────────────┘
```

### 9e. AI-Assisted Merge Conflict

```
Kalau git_pull atau git_merge menghasilkan conflict:
  │
  ▼
Agent detect file yang conflict (ada <<<<<<< markers)
  │
  ▼
Agent baca kedua versi per conflict:
  "ours"   → versi branch kamu
  "theirs" → versi yang mau di-merge
  │
  ▼
LLM analisis dan suggest resolusi:
  "Conflict di baris 42-58 di core/agent_loop.py.
   Versi 'ours' tambah mode_manager, versi 'theirs' refactor imports.
   Suggest: ambil keduanya — import dulu, lalu mode_manager."
  │
  ▼
Tampilkan ke user:
  - Penjelasan conflict
  - Suggestion resolusi
  - Preview hasil kalau suggestion diikuti
  │
  ▼
User decide → kalau setuju → agent apply resolusi + mark as resolved
             kalau tidak → user resolve manual
```

---

## 10. System Prompt Composition

Ini yang "nyusun" instruksi lengkap ke LLM setiap kali kirim request.

### Urutan Komposisi

```
System Prompt = [1] + [2] + [3] + [4]

[1] Soul
    Konten dari soul.md
    (kepribadian, cara bicara, nilai)

[2] Project Context
    Hasil dari codebase awareness:
    nama project, jenis, struktur, dependencies, git status

[3] Mode Instructions
    Instruksi spesifik untuk mode yang aktif (/code, dll)
    Daftar tool yang tersedia di mode ini

[4] Operational Rules
    Aturan teknis yang selalu berlaku:
    - Format output
    - Cara handle permission
    - Batas tool iterations
```

### Implementasi

```
core/prompt_composer.py:
  Class PromptComposer
    compose(soul, project_ctx, mode, rules)  → return string system prompt
    update_project_ctx(new_ctx)              → update bagian project context
    get_prompt()                             → return prompt yang sudah tersusun
```

### Kapan System Prompt Diupdate

```
Saat startup          → compose semua dari awal
Ganti mode (/code)    → update bagian [3] saja
Re-scan (/scan)       → update bagian [2] saja
Ganti soul            → update bagian [1] saja (sesi berikutnya)
```

---

## 11. TUI Enhancement

### 11a. Status Bar (update dari Phase 1)

```
Phase 1:
  ⚡ multacd  ·  💻 coding  ·  claude-sonnet-4-6  ·  ●

Phase 2:
  ⚡ multacd  ·  💻 code  ·  claude-sonnet-4-6  ·  📍 main +3  ·  ●

Tambahan: "📍 main +3" = branch git aktif + jumlah file modified
Warna mode: hijau=/code, biru=/research, ungu=/personal
```

### 11b. File Tree Panel (baru)

```
Toggle: Ctrl+T

Layout saat aktif:
┌──────────────┬─────────────────────────────────────┐
│ 📁 myapp     │                                     │
│  ├ core/     │   [Chat Panel]                      │
│  │ ├ config  │                                     │
│  │ └ agent.. │                                     │
│  ├ tools/    │                                     │
│  ├ tui/      │                                     │
│  └ main.py   │                                     │
├──────────────┴─────────────────────────────────────┤
│  ❯ _                                               │
└────────────────────────────────────────────────────┘

Fitur file tree:
  - Highlight file yang sedang dibahas di chat
  - Warna berbeda untuk file yang modified (git)
  - Klik atau Enter pada file → agent baca file itu
```

### 11c. Diff Viewer (baru)

```
Ditampilkan saat:
  - Agent mau commit (show summary dulu)
  - User minta lihat perubahan
  - Conflict resolution

Toggle: Ctrl+D

Format:
┌─ Git Diff ─────────────────────────────────────────┐
│ M core/agent_loop.py  +45 / -12                    │
│ A core/codebase.py    +230 / -0                    │
│                                                    │
│ @@ -38,6 +38,12 @@                                │
│ - old_line = "something"                           │  ← merah
│ + new_line = "something_better"                   │  ← hijau
└────────────────────────────────────────────────────┘
```

### 11d. Progress Indicator (baru)

```
Saat codebase scan berjalan:
  "🔍 Scanning project... (47 files)"

Saat test runner berjalan:
  "🧪 Running tests... (12/24 passed)"

Saat agent sedang loop tool:
  "⚙️  Thinking... (tool 3/20)"
```

---

## 12. Step-by-Step Build Phase 2

> Ikuti urutan ini. Tiap step bergantung pada yang sebelumnya.

---

### Step 1 — soul.md System

**Tujuan:** Agent punya kepribadian yang konsisten.

```
Tugas:
  [ ] Pastikan soul.md sudah ada di root project
      (file ini sudah dibuat sebagai planning doc — sekarang
       jadikan file resmi yang dibaca oleh aplikasi)
  [ ] Buat core/prompt_composer.py:
        - Fungsi load_soul(config_dir, project_dir):
            · Cek ~/.multacd/soul.md dulu
            · Kalau tidak ada → load soul.md dari root project
            · Return konten sebagai string
        - Class PromptComposer (skeleton dulu, diisi step-step berikutnya)
  [ ] Test: load_soul() berhasil return konten soul.md

Hasil: soul.md terbaca, konten tersedia untuk diinjek ke prompt.
```

---

### Step 2 — Mode Manager

**Tujuan:** System bisa ganti mode dan parse command (/code, /help, dll).

```
Tugas:
  [ ] Buat core/mode_manager.py:
        - Definisikan MODE_CODE, MODE_RESEARCH, MODE_PERSONAL sebagai konstanta
        - Class ModeManager:
            · __init__() → set default mode ke /code
            · handle_command(user_input) → return (is_command, result):
                Kalau input mulai dengan "/" → parse command
                Kalau bukan → return (False, None)
            · set_mode(mode) → ganti mode, return pesan konfirmasi
            · get_mode_prompt() → return instruksi tambahan untuk mode ini
            · get_active_tools() → return list tool yang aktif

  [ ] Implementasikan semua command:
        /code      → set_mode("code")
        /research  → "belum tersedia (Phase 3)"
        /personal  → "belum tersedia (Phase 4)"
        /clear     → return signal untuk clear context
        /scan      → return signal untuk trigger scan ulang
        /model X   → update config model, return konfirmasi
        /model     → return nama model aktif
        /help      → return string daftar semua command
        /soul      → return konten soul.md yang aktif

  [ ] Update core/agent_loop.py:
        - Sebelum proses input → cek mode_manager.handle_command()
        - Kalau command → handle, jangan kirim ke LLM
        - Kalau bukan command → proses seperti biasa

Hasil: Semua command / jalan, mode bisa diganti, agent_loop mengenalinya.
```

---

### Step 3 — Codebase Awareness

**Tujuan:** Agent otomatis baca dan ngerti project saat startup.

```
Tugas:
  [ ] Buat core/codebase.py:
        - Fungsi detect_project_type(root_path):
            Cek file signature → return jenis project
        - Fungsi get_key_files(root_path):
            Baca README.md, .env.example, requirements.txt, pyproject.toml,
            setup.py, Makefile, docker-compose.yml
            TIDAK BACA: PLAN.md, ROADMAP.md, soul.md
            Return dict {filename: content}
        - Fungsi build_file_tree(root_path, depth=3):
            Rekursif list folder/file
            Skip: .git/, .venv/, node_modules/, __pycache__/
            Skip semua yang ada di .gitignore
            Return string tree yang bisa dibaca
        - Fungsi get_git_summary(root_path):
            Branch aktif, jumlah modified, jumlah untracked
            Return dict
        - Fungsi scan_project(root_path):
            Gabungkan semua → return ProjectContext string

  [ ] Buat tools/codebase/scan_codebase.py:
        - Tool yang bisa dipanggil agent secara manual
        - Panggil scan_project() dan return hasilnya

  [ ] Update main.py / tui/app.py:
        - Saat startup → panggil scan_project() di working directory
        - Tampilkan progress indicator saat scan berjalan
        - Simpan hasil ke session state

  [ ] Update core/prompt_composer.py:
        - Tambahkan project context ke komposisi prompt
        - Fungsi compose() → gabungkan soul + project context + mode

Hasil: Saat multacd dibuka, agent sudah "tahu" project apa yang dibuka.
```

---

### Step 4 — Code Execution Tool

**Tujuan:** Agent bisa jalankan file Python dan snippet.

```
Tugas:
  [ ] Buat tools/code/run_python.py:
        - Fungsi detect_python(root_path):
            Cek .venv/bin/python → pakai itu
            Kalau tidak ada → cek python3, python di PATH
            Return path ke python executable
        - Fungsi run_python(file_path=None, code=None, args=[], timeout=30):
            Validasi: file_path atau code harus diisi, tidak boleh dua-duanya None
            Kalau code (snippet) → tulis ke temp file dulu
            Jalankan dengan subprocess + streaming output
            Handle timeout → kill process kalau melebihi batas
            Return {success, stdout, stderr, exit_code, duration}
        - Stream stdout/stderr ke TUI real-time (bukan nunggu selesai)

  [ ] Register di tools/registry.py dengan permission: ASK

  [ ] Update tools/registry.py:
        - Tambahkan run_python ke tool definitions
        - Format JSON Schema yang LLM mengerti

  [ ] Test manual:
        - run_python(code="print('hello')") → sukses
        - run_python(code="1/0") → gagal, traceback di stderr
        - run_python(code="import time; time.sleep(60)", timeout=5) → timeout

Hasil: Agent bisa jalankan Python, output streaming, timeout berjalan.
```

---

### Step 5 — Code Quality Tools

**Tujuan:** Agent bisa lint dan test kode.

```
Tugas:
  [ ] Install ruff dan pytest (tambahkan ke requirements.txt dan install)

  [ ] Buat tools/code/lint_python.py:
        - Fungsi lint_python(path, fix=False):
            Jalankan: ruff check {path} [--fix]
            Parse output ruff → list {file, line, col, code, message}
            Return {success, issues, fixed_count, summary}
        - Permission: AUTO kalau fix=False, ASK kalau fix=True

  [ ] Buat tools/code/run_tests.py:
        - Fungsi run_tests(path=".", test_name=None, verbose=False):
            Jalankan: pytest {path} [-k test_name] [-v] --tb=short
            Parse output pytest → {passed, failed, errors, skipped, duration}
            Parse detail per test yang gagal
            Return semua info tersebut
        - Permission: ASK

  [ ] Register kedua tool di tools/registry.py

  [ ] Test manual:
        - Buat file Python dengan syntax error → lint_python detect
        - Buat file test sederhana → run_tests jalan

Hasil: Agent bisa lint kode dan jalankan test suite.
```

---

### Step 6 — Smart Git Flow

**Tujuan:** Git workflow yang cerdas — preview, protect, AI-assisted.

```
Tugas:
  [ ] Auto git_status saat startup:
        - Di tui/app.py atau main.py → jalankan git_status setelah scan
        - Update status bar dengan info branch + changed files
        - Kalau bukan git repo → status bar "no git", nonaktifkan git tools

  [ ] LLM-generated commit message:
        - Di tools/git/git_commit.py:
            Sebelum commit → jalankan git_diff dulu (otomatis)
            Kirim diff ke LLM dengan prompt: "Generate conventional commit message"
            Return message yang di-generate
        - Di TUI: tampilkan message + tombol [Pakai ini] / [Edit dulu]
        - Setelah user approve/edit → baru jalankan commit

  [ ] Branch protection di tools/git/git_push.py:
        - Definisikan PROTECTED_BRANCHES = ["main", "master", "production",
          "prod", "release", "stable"]
        - Cek branch target sebelum push
        - Kalau protected → tampilkan warning extra + opsi "Buat branch baru"

  [ ] AI-assisted merge conflict di tools/git/git_merge.py (baru):
        - Detect conflict markers (<<<<<<< ======= >>>>>>>)
        - Parse kedua versi (ours vs theirs) per conflict
        - Kirim ke LLM → minta analisis + suggestion
        - Tampilkan suggestion ke user
        - Kalau user setuju → apply resolusi + `git add` file

  [ ] Update status bar secara periodik:
        - Setiap beberapa detik → refresh git status di background
        - Update status bar tanpa interrupt chat

Hasil: Git workflow lebih cerdas, aman, dan ada AI di dalamnya.
```

---

### Step 7 — System Prompt Composition

**Tujuan:** LLM menerima context yang lengkap dan terstruktur setiap request.

```
Tugas:
  [ ] Lengkapi core/prompt_composer.py:
        - Class PromptComposer:
            __init__(soul, project_ctx, mode_manager)
            compose() → return string system prompt lengkap
                        urutan: soul → project_ctx → mode_prompt → rules
            update_project_ctx(new_ctx) → update bagian project
            update_mode() → update bagian mode (saat ganti /code dll)

  [ ] Definisikan operational rules (bagian [4]):
        String yang selalu ada di akhir system prompt:
        - Format output (markdown, code blocks)
        - Batas tool iterations
        - Cara handle error

  [ ] Update core/agent_loop.py:
        - Pakai prompt_composer.compose() untuk system prompt
        - Bukan hardcoded string lagi

  [ ] Test: print system prompt yang dihasilkan, pastikan lengkap dan urut

Hasil: LLM selalu dapat context soul + project + mode yang lengkap.
```

---

### Step 8 — TUI Enhancement

**Tujuan:** TUI lebih informatif dan nyaman untuk coding workflow.

```
Tugas:
  [ ] Update tui/widgets/status_bar.py:
        - Tambah slot untuk: mode (dengan warna), git branch, git changed count
        - Fungsi update_git_status(branch, changed) → update display
        - Fungsi update_mode(mode) → update warna & label mode

  [ ] Buat tui/widgets/file_tree.py:
        - Panel kiri yang bisa di-toggle dengan Ctrl+T
        - Render file tree dari hasil scan_project()
        - Highlight file yang modified di git (warna berbeda)
        - Enter/klik pada file → kirim "baca file {path}" ke agent

  [ ] Buat tui/widgets/diff_viewer.py:
        - Panel yang muncul saat ada diff untuk ditampilkan
        - Syntax highlight: merah untuk baris hapus, hijau untuk tambah
        - Toggle dengan Ctrl+D
        - Dipanggil oleh git_commit flow sebelum user approve

  [ ] Tambah progress indicators:
        - Saat scan codebase: spinner + "Scanning project..."
        - Saat run_tests: "Running tests... (X/Y)"
        - Saat agent loop: sudah ada, pastikan masih jalan

  [ ] Update tui/screens/main_screen.py:
        - Susun layout baru: file_tree (opsional) + chat_panel
        - Handle Ctrl+T toggle file_tree
        - Handle Ctrl+D toggle diff_viewer

Hasil: TUI lebih kaya informasi, file tree dan diff viewer bisa dipakai.
```

---

### Step 9 — Wire Everything & Polish

**Tujuan:** Semua komponen Phase 2 tersambung dan jalan bersama.

```
Tugas:
  [ ] Update main.py / tui/app.py — urutan startup:
        1. Load config
        2. Load soul.md (prompt_composer)
        3. Scan codebase → project_ctx (prompt_composer)
        4. Init mode_manager (default: /code)
        5. Compose system prompt
        6. Init agent_loop dengan prompt baru
        7. Run git_status → update status bar
        8. Tampilkan TUI

  [ ] Pastikan mode_manager tersambung ke:
        - agent_loop (untuk parse / commands)
        - prompt_composer (untuk update mode prompt)
        - status_bar (untuk update display)

  [ ] Pastikan git flow tersambung ke:
        - diff_viewer (tampilkan diff sebelum commit)
        - status_bar (update branch info)
        - confirm_dialog (branch protection warning)

  [ ] Test end-to-end:
        - Buka multacd di folder project → scan berjalan
        - Tanya agent tentang project → dia ngerti structurenya
        - Minta run file Python → konfirmasi muncul, output streaming
        - Minta lint kode → hasil tampil per baris
        - Minta commit → diff preview + generated message muncul
        - Ketik /model gpt-4o → model ganti on-the-fly
        - Ctrl+T → file tree muncul/hilang

  [ ] Error handling final:
        - Folder bukan git repo → git tools gracefully disabled
        - ruff tidak terinstall → lint_python kasih pesan install dulu
        - pytest tidak terinstall → run_tests kasih pesan install dulu
        - Scan codebase gagal → fallback ke minimal context, tidak crash

Hasil: Phase 2 selesai, semua fitur jalan terintegrasi.
```

---

## 13. Deliverable Phase 2

```
soul.md & Personality
  ✅ soul.md terbaca dan di-inject ke setiap sesi
  ✅ User bisa override dengan ~/.multacd/soul.md
  ✅ Agent bicara dengan karakter yang konsisten

Codebase Awareness
  ✅ Auto-scan saat startup
  ✅ Baca file kunci project (README, requirements, dll)
  ✅ Build file tree (ignore .venv, __pycache__, dll)
  ✅ Deteksi jenis project
  ✅ TIDAK scan PLAN.md / ROADMAP.md
  ✅ Agent langsung "ngerti" project tanpa user jelasin

Mode Switching
  ✅ /code aktif dan berfungsi penuh
  ✅ /research dan /personal ada tapi placeholder (Phase 3 & 4)
  ✅ /clear, /scan, /model, /help, /soul semua jalan
  ✅ Status bar update sesuai mode aktif

Code Execution
  ✅ run_python jalankan file .py dan snippet
  ✅ Deteksi virtual environment otomatis
  ✅ Streaming output real-time
  ✅ Timeout protection (default 30 detik)
  ✅ Kalau error → agent analisis + suggest fix

Code Quality
  ✅ lint_python dengan ruff → hasil per baris
  ✅ run_tests dengan pytest → summary + detail yang gagal
  ✅ Kalau test gagal → agent analisis penyebab

Smart Git Flow
  ✅ Auto git_status saat startup di status bar
  ✅ LLM generate conventional commit message
  ✅ Diff preview sebelum commit
  ✅ Branch protection untuk main/master/production
  ✅ AI suggestion untuk merge conflict

TUI
  ✅ Status bar: mode + branch + changed files
  ✅ File tree panel (toggle Ctrl+T)
  ✅ Diff viewer (toggle Ctrl+D)
  ✅ Progress indicators untuk operasi panjang
```

---

*multacd PLAN-phase2.md*
*Bangun di atas Phase 1. Jangan lupa update ROADMAP.md saat selesai.*
