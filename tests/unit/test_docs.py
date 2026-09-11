"""Guard docs (Phase 5 Step 7) — nav mkdocs sinkron dengan file."""

from __future__ import annotations

from pathlib import Path

import yaml

DOCS = Path(__file__).resolve().parent.parent.parent / "docs"


def _nav_files(nav: list) -> list[str]:
    out: list[str] = []
    for item in nav:
        if isinstance(item, dict):
            for v in item.values():
                if isinstance(v, str):
                    out.append(v)
                elif isinstance(v, list):
                    out.extend(_nav_files(v))
    return out


def test_nav_files_exist():
    cfg = yaml.safe_load((DOCS / "mkdocs.yml").read_text(encoding="utf-8"))
    files = _nav_files(cfg["nav"])
    assert len(files) >= 7  # index, install, quickstart, config, 3 mode, plugin
    for f in files:
        assert (DOCS / f).is_file(), f


def test_core_files_exist():
    for f in ("README.md", "CHANGELOG.md", "CONTRIBUTING.md"):
        assert (DOCS.parent / f).is_file(), f
