"""Unit: bash valid + timeout graceful."""

from __future__ import annotations

from tools.shell.bash import bash


def test_bash_echo():
    r = bash("echo halo")
    assert r["success"] and "halo" in r["result"]


def test_bash_timeout_graceful():
    r = bash("sleep 5", timeout=1)
    assert not r["success"] and "timeout" in r["error"].lower()


def test_bash_bad_exit_code_still_ok_with_marker():
    r = bash("exit 3")
    assert r["success"] and "exit code: 3" in r["result"]
