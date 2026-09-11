"""Unit: write_file bikin folder otomatis + overwrite."""

from __future__ import annotations

from pathlib import Path

from tools.filesystem.write_file import write_file


def test_write_creates_parent_dirs(workdir: Path):
    target = workdir / "sub" / "deep" / "b.txt"
    r = write_file(str(target), "isi")
    assert r["success"]
    assert target.read_text(encoding="utf-8") == "isi"


def test_write_overwrite(workdir: Path):
    target = workdir / "c.txt"
    target.write_text("lama", encoding="utf-8")
    r = write_file(str(target), "baru")
    assert r["success"] and "overwrite" in r["result"].lower()
    assert target.read_text(encoding="utf-8") == "baru"
