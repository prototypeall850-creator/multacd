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
> Search (tavily/exa/brave/serpapi/duckduckgo) native httpx — tanpa SDK,
> tanpa Rust, jalan di HP. Cukup isi `search_api_key` (gratis: duckduckgo).

## Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/prototypeall850-creator/multacd/main/scripts/install.ps1 | iex
```

## Via pip (semua OS)

```bash
pip install multacd            # stable v1 (1.0.0)
pip install "multacd==2.0.0b10"  # kanal beta v2 (pin — v2 masih prerelease)
multacd --version
```

## Dari source (buat ngoprek)

```bash
git clone https://github.com/prototypeall850-creator/multacd && cd multacd
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python main.py
```
