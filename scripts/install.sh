#!/usr/bin/env bash
# install.sh — multacd installer (Linux / macOS / Termux). Phase 5 Step 6.
#   curl -fsSL https://raw.githubusercontent.com/prototypeall850-creator/multacd/main/scripts/install.sh | bash
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

pip_fallback() {
    echo "Install binary gagal / platform belum ada binary-nya."
    echo "Alternatif via pip (butuh Python 3.10+):"
    echo "  pip install \"git+https://github.com/$REPO\""
    echo "Lalu jalankan: multacd"
}

main() {
    local platform url tmp dest_dir dest
    platform="$(detect_platform)"
    if [ "$platform" = "unsupported" ]; then
        pip_fallback
        exit 1
    fi
    echo "Installing multacd untuk $platform..."

    url="$BINARY_BASE/multacd-$platform"
    tmp="$(mktemp)"
    # shellcheck disable=SC2064
    trap "rm -f '$tmp'" EXIT
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$url" -o "$tmp" || { pip_fallback; exit 1; }
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$tmp" "$url" || { pip_fallback; exit 1; }
    else
        echo "Butuh curl atau wget." >&2
        pip_fallback
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
        echo "Binary terinstall di $dest tapi gagal jalan." >&2
        pip_fallback
        exit 1
    fi
}

if [ "${BASH_SOURCE[0]:-}" = "$0" ]; then
    main "$@"
fi
