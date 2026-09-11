# install.ps1 — multacd installer (Windows). Phase 5 Step 6.
#   irm https://raw.githubusercontent.com/prototypeall850-creator/multacd/main/scripts/install.ps1 | iex
#
# Override (mirror sendiri): $env:MULTACD_REPO, $env:MULTACD_BINARY_BASE,
# $env:MULTACD_INSTALL_DIR.

$ErrorActionPreference = "Stop"

$Repo = if ($env:MULTACD_REPO) { $env:MULTACD_REPO } else { "prototypeall850-creator/multacd" }
$BinaryBase = if ($env:MULTACD_BINARY_BASE) { $env:MULTACD_BINARY_BASE } else { "https://github.com/$Repo/releases/latest/download" }
$InstallDir = if ($env:MULTACD_INSTALL_DIR) { $env:MULTACD_INSTALL_DIR } else { "$env:LOCALAPPDATA\multacd" }

Write-Host "Installing multacd untuk windows-x86_64..."

if (-not [Environment]::Is64BitOperatingSystem) {
    Write-Host "Windows 32-bit belum ada binary-nya. Alternatif via pip (Python 3.10+):"
    Write-Host "  pip install `"git+https://github.com/$Repo`""
    exit 1
}

$BinaryUrl = "$BinaryBase/multacd-windows-x86_64.exe"
$BinaryPath = Join-Path $InstallDir "multacd.exe"

try {
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Invoke-WebRequest -Uri $BinaryUrl -OutFile $BinaryPath -UseBasicParsing
}
catch {
    Write-Host "Download gagal: $($_.Exception.Message)"
    Write-Host "Alternatif via pip (Python 3.10+):"
    Write-Host "  pip install `"git+https://github.com/$Repo`""
    exit 1
}

$CurrentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($CurrentPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$CurrentPath;$InstallDir", "User")
    Write-Host "Ditambahkan ke PATH (buka terminal baru agar berlaku)."
}

try {
    $Ver = & $BinaryPath --version 2>$null
    Write-Host "multacd berhasil diinstall: $Ver"
    Write-Host "Buka terminal baru dan jalankan: multacd"
}
catch {
    Write-Host "Binary terinstall di $BinaryPath tapi gagal jalan: $($_.Exception.Message)"
    exit 1
}
