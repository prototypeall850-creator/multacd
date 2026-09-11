"""Unit: permission auto / ask / override config / session [A]."""

from __future__ import annotations

from core.config import Config
from core.permissions import PermissionChecker, check_permission


def test_auto_tools():
    for t in ("read_file", "glob", "git_status", "web_search", "get_jobs"):
        assert check_permission(t) == "auto", t


def test_ask_tools():
    for t in ("write_file", "bash", "web_fetch", "run_python",
              "quick_research", "schedule_job", "cancel_job"):
        assert check_permission(t) == "ask", t


def test_unknown_denied():
    assert check_permission("rm_rf_semua") == "deny"
    assert check_permission("") == "deny"


def test_paranoid_reads_become_ask():
    paranoid = Config(model="m", api_key="k", auto_approve_reads=False)
    assert check_permission("read_file", paranoid) == "ask"
    # meta & git tidak terpengaruh override read
    assert check_permission("recall", paranoid) == "auto"
    assert check_permission("git_status", paranoid) == "auto"


def test_yolo_still_asks_code_and_research():
    yolo = Config(model="m", api_key="k", auto_approve_reads=True,
                  ask_before_write=False, ask_before_bash=False,
                  ask_before_web=False)
    assert check_permission("write_file", yolo) == "auto"
    assert check_permission("run_python", yolo) == "ask"
    assert check_permission("quick_research", yolo) == "ask"
    assert check_permission("schedule_job", yolo) == "ask"


def test_session_approve_resets_per_instance():
    c = PermissionChecker()
    assert c.check("write_file") == "ask"
    c.approve_all_for_session("write_file")
    assert c.check("write_file") == "auto"
    assert PermissionChecker().check("write_file") == "ask"


def test_session_approve_blocked_for_risky():
    c = PermissionChecker()
    c.approve_all_for_session("run_python")
    assert c.check("run_python") == "ask"
    c.approve_all_for_session("delete_file")
    assert c.check("delete_file") == "ask"
