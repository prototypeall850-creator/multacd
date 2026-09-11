# multacd.spec — PyInstaller build.
# Build lokal:  pyinstaller multacd.spec   → dist/multacd
# CI: matrix platform, output diganti per OS.
#
# NOTE v2: provider native via httpx (wheel murni),
# jadi tak perlu collect data/hiddenimports berat lagi.
# Binary susut signifikan dibanding era sebelum v2.

# ruff: noqa — Analysis/PYZ/EXE/collect_data_files adalah global PyInstaller.

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("soul.md", "."),
        ("plugins/example_plugin.py", "plugins"),
        ("plugins/README.md", "plugins"),
    ],
    hiddenimports=[
        # Package kita yang diimport lazy (agent_loop, daemon, bot).
        "tools.registry",
        "core.agent_loop",
        "core.plugin_loader",
        "core.updater",
        "core.providers.openai_compat",
        "core.providers.anthropic",
        "scheduler.engine",
        "tg.bot",
        "tg.agent",
        "daemon.process",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PySide6", "matplotlib", "notebook"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="multacd",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # reproducible + hindari false-positive antivirus
    console=True,  # TUI butuh console mode
    onefile=True,
)
