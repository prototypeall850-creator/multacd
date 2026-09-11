"""Unit: read_file happy path + error case."""

from __future__ import annotations

from pathlib import Path

from tools.filesystem.read_file import read_file


def test_read_existing(workdir: Path):
    p = workdir / "a.txt"
    p.write_text("halo", encoding="utf-8")
    r = read_file(str(p))
    assert r["success"] and r["result"] == "halo"


def test_read_missing_returns_error(workdir: Path):
    r = read_file(str(workdir / "tidak-ada.txt"))
    assert not r["success"] and "tidak ditemukan" in r["error"].lower()


def test_read_directory_returns_error(workdir: Path):
    r = read_file(str(workdir))
    assert not r["success"]
