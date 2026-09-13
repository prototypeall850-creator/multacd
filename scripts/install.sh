#!/usr/bin/env bash
# install.sh — multacd installer (Linux / macOS / Termux).
#
# Cara pakai (download dulu biar gagalnya kelihatan — JANGAN pipe-buta):
#   curl -fSL https://raw.githubusercontent.com/prototypeall850-creator/multacd/main/scripts/install.sh -o ./m-install.sh \
#     && bash ./m-install.sh && rm ./m-install.sh
# Pipe `curl ... | bash` menelan error curl (stdin bash kosong = diam saja).
# NOTE Termux: jangan pakai /tmp (tidak ada) — ./ (cwd) selalu bisa ditulis.
#
# Env override (buat test / mirror sendiri):
#   MULTACD_REPO         "owner/repo" (default: prototypeall850-creator/multacd)
#   MULTACD_BINARY_BASE  base URL rilis (default: .../releases/latest/download)
#   MULTACD_INSTALL_DIR  folder tujuan (default: /usr/local/bin atau ~/.local/bin)

set -eu

REPO="${MULTACD_REPO:-prototypeall850-creator/multacd}"
BINARY_BASE="${MULTACD_BINARY_BASE:-https://github.com/$REPO/releases/latest/download}"

detect_platform() {
    local os arch
    os="$(uname -s)"
    arch="$(uname -m)"
    case "$os" in
        Linux)
            if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux" ]; then
                echo "termux-aarch64"
            elif [ "$arch" = "aarch64" ] || [ "$arch" = "arm64" ]; then
                echo "linux-aarch64"
            elif [ "$arch" = "x86_64" ]; then
                echo "linux-x86_64"
            else
                echo "unsupported"
            fi
            ;;
        Darwin)
            if [ "$arch" = "arm64" ]; then
                echo "macos-arm64"
            else
                echo "macos-x86_64"
            fi
            ;;
        *)
            echo "unsupported"
            ;;
    esac
}

is_termux() {
    [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux" ]
}

pip_fallback() {
    # $1 = sebab (opsional): ditampilkan di baris pertama biar diagnosa jelas.
    if [ -n "${1:-}" ]; then
        echo "Gagal: $1" >&2
    fi
    if is_termux; then
        # Jujur: binary rilis (build ubuntu glibc) TIDAK jalan di Termux
        # (bionic libc) — Termux wajib jalur pip.
        termux_pip_guide
        exit 1
    fi
    echo "Install binary gagal / platform belum ada binary-nya."
    echo "Alternatif via pip (butuh Python 3.10+):"
    echo "  pip install \"git+https://github.com/$REPO\""
    echo "Lalu jalankan: multacd"
}

termux_pip_guide() {
    # Pin beta exact TANPA --pre: pip tetap boleh install versi beta yang
    # dipin, sementara dependensi resolve ke versi stabil (anti httpx-dev /
    # apscheduler-alpha / pydantic-beta). --pre bocor ke semua deps!
    echo "Termux terdeteksi — pakai jalur pip (binary rilis tidak kompatibel)."
    echo ""
    echo "  1. Siapkan toolchain (sekali saja):"
    echo "     pkg install -y python git curl"
    echo "     (ringan: tanpa kompilasi Rust — dependensi wheel murni)"
    echo ""
    echo "  2. Install multacd:"
    echo "     pip install \"multacd==2.0.0b9\""
    echo ""
    echo "  3. Jalankan: multacd"
    echo ""
    echo "  Opsional (provider search Exa, butuh Rust — lewati kalau ragu):"
    echo "     pip install \"multacd[exa]\""
}

main() {
    local platform url tmp dest_dir dest
    # Termux: tidak ada binary yang kompatibel (glibc vs bionic) — jangan
    # buang waktu nyoba unduh URL yang pasti 404, langsung panduan pip.
    if is_termux; then
        termux_pip_guide
        exit 1
    fi
    platform="$(detect_platform)"
    if [ "$platform" = "unsupported" ]; then
        pip_fallback "platform tidak dikenal ($(uname -s)/$(uname -m))."
        exit 1
    fi
    echo "Installing multacd untuk $platform..."

    url="$BINARY_BASE/multacd-$platform"
    tmp="$(mktemp)"
    # shellcheck disable=SC2064
    trap "rm -f '$tmp'" EXIT
    if command -v curl >/dev/null 2>&1; then
        curl -fSL "$url" -o "$tmp" || {
            pip_fallback "unduh binary gagal dari $url (cek koneksi/TLS; pastikan 'pkg install curl' di Termux)"
            exit 1
        }
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$tmp" "$url" || {
            pip_fallback "unduh binary gagal dari $url (cek koneksi/TLS)"
            exit 1
        }
    else
        pip_fallback "butuh curl atau wget (Termux: pkg install curl)."
        exit 1
    fi
    if [ ! -s "$tmp" ]; then
        pip_fallback "file terunduh kosong dari $url."
        exit 1
    fi
    chmod +x "$tmp"

    if [ -n "${MULTACD_INSTALL_DIR:-}" ]; then
        dest_dir="$MULTACD_INSTALL_DIR"
        mkdir -p "$dest_dir"
    elif [ -w "/usr/local/bin" ]; then
        dest_dir="/usr/local/bin"
    else
        dest_dir="$HOME/.local/bin"
        mkdir -p "$dest_dir"
    fi
    dest="$dest_dir/multacd"
    mv "$tmp" "$dest"

    case ":$PATH:" in
        *":$dest_dir:"*) ;;
        *) echo "NOTE: $dest_dir belum ada di PATH — tambahkan agar 'multacd' bisa dipanggil." ;;
    esac

    if "$dest" --version >/dev/null 2>&1; then
        echo "multacd berhasil diinstall: $("$dest" --version)"
        echo "Jalankan: multacd"
    else
        pip_fallback "binary terinstall di $dest tapi gagal jalan (kemungkinan libc tidak cocok)."
        exit 1
    fi
}

if [ "${BASH_SOURCE[0]:-}" = "$0" ]; then
    main "$@"
fi
