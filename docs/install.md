# Install

Syarat: Python 3.10+. Tiga cara, pilih satu.

## Binary (Linux / macOS / Termux)

```bash
curl -fsSL https://raw.githubusercontent.com/prototypeall850-creator/multacd/main/scripts/install.sh | bash
```

> Binary tersedia mulai rilis **v1.0.0**. Sebelum itu pakai cara pip/git di bawah.

## Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/prototypeall850-creator/multacd/main/scripts/install.ps1 | iex
```

## Via pip (semua OS)

```bash
pip install "git+https://github.com/prototypeall850-creator/multacd"
multacd --version
```

Setelah v1.0.0 terbit di PyPI: `pip install multacd`.

## Dari source (buat ngoprek)

```bash
git clone https://github.com/prototypeall850-creator/multacd && cd multacd
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python main.py
```
