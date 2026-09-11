# multacd.spec — PyInstaller build (Phase 5 Step 5).
# Build lokal:  pyinstaller multacd.spec   → dist/multacd
# CI (Step 9):  matrix 5 platform, output diganti per OS.

# ruff: noqa — Analysis/PYZ/EXE/collect_data_files adalah global PyInstaller.

from PyInstaller.utils.hooks import collect_data_files

_litellm_data = collect_data_files("litellm")
_tiktoken_data = collect_data_files("tiktoken")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("soul.md", "."),
        ("plugins/example_plugin.py", "plugins"),
        ("plugins/README.md", "plugins"),
        *_litellm_data,
        *_tiktoken_data,
    ],
    hiddenimports=[
        # tiktoken registry encoding (dibutuhkan litellm token counter).
        "tiktoken_ext.openai_public",
        "tiktoken_ext",
        # LiteLLM load provider dinamis (importlib) — tak kedetek statis.
        "litellm",
        "litellm.litellm_core_utils",
        "litellm.llms",
        "litellm.providers",
        # Provider spesifik yang dipakai via LiteLLM routing.
        "anthropic",
        "openai",
        "google",
        "groq",
        "ollama",
        # Package kita yang diimport lazy (agent_loop, daemon, bot).
        "tools.registry",
        "core.agent_loop",
        "core.plugin_loader",
        "core.updater",
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
