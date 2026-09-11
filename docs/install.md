# Install

Syarat: Python 3.10+. Tiga cara, pilih satu.

## Binary (Linux / macOS / Windows)

```bash
curl -fSL https://raw.githubusercontent.com/prototypeall850-creator/multacd/main/scripts/install.sh -o ./m-install.sh \
  && bash ./m-install.sh && rm ./m-install.sh
```

> Jangan pipe `curl | bash` (error curl ketelen, installer diam saja).
> Binary rilis TIDAK jalan di Termux (glibc vs bionic) — Termux pakai pip.

## Termux (wajib pip)

```bash
pkg install -y python git curl
pip install "multacd==2.0.0b4"
multacd
```

> Pin beta exact TANPA `--pre` (`--pre` bocor ke semua dependensi).
> Dependensi default murni wheel (tanpa Rust). Opsional:
> `pip install "multacd[exa]"` / `"multacd[tavily]"` (butuh Rust, lewati di HP).

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
