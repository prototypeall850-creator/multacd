# Contributing to multacd

## Setup development

```bash
git clone https://github.com/prototypeall850-creator/multacd && cd multacd
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Menjalankan tests

```bash
pytest tests/            # semua (butuh ~1 menit)
pytest tests/unit/       # cepat, tanpa self-test modul
./.venv/bin/ruff check . # lint wajib hijau sebelum commit
```

Setiap modul inti punya self-test (`python -m <modul>`) yang ikut
dijalankan `tests/test_selftests.py` — pola ini jangan dihapus.

## Membuat plugin

Lihat `plugins/README.md` + `docs/plugins.md`. Test plugin:

```bash
cp pluginmu.py ~/.multacd/plugins/ && multacd
```

## Pull request

- Fork → branch `feature/nama-fitur` → PR ke `main`
- Commit: `<EMOJI> <TYPE>: Pesan` (maks 50 karakter — cth `🔌 NEW: ...`)
- Wajib: `ruff` bersih + `pytest tests/` hijau
- Update `CHANGELOG.md` ([Unreleased]) kalau ubah perilaku user
- Issue kecil/bug? Buka issue dulu biar tercatat
