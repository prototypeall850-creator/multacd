# Coding Agent (/code)

Default mode. Agent sadar codebase (auto-scan saat startup),
bisa baca/tulis file, jalanin `bash`, `run_python`, `lint_python`,
`run_tests`, dan smart git flow (diff preview, proteksi branch utama).

- Tool baca & git langsung jalan; tulis/shell/eksekusi minta izin
  dulu (popup Y/N/A di TUI).
- `/scan` untuk scan ulang, `/model` untuk ganti model,
  `Ctrl+T` file tree, `Ctrl+G` diff viewer.
