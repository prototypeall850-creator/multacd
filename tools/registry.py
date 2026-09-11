"""Registry — daftar & routing semua tool + definisi JSON Schema buat LLM.

    from tools.registry import get_tool_definitions, execute_tool

    tools = get_tool_definitions()          # → [SCHEMA, ...] untuk LLM
    result = execute_tool("read_file", {"path": "main.py"})
"""

from __future__ import annotations

import inspect
import traceback
from collections.abc import Callable
from typing import Any

from core.permissions import KNOWN_TOOLS
from tools.agent.ask import SCHEMA as ASK_SCHEMA
from tools.agent.ask import ask
from tools.agent.skill import SCHEMA as SKILL_SCHEMA
from tools.agent.skill import skill
from tools.agent.task import SCHEMA as TASK_SCHEMA
from tools.agent.task import task
from tools.agent.todo_write import SCHEMA as TODO_WRITE_SCHEMA
from tools.agent.todo_write import todo_write
from tools.code.lint_python import SCHEMA as LINT_PYTHON_SCHEMA
from tools.code.lint_python import lint_python
from tools.code.run_python import SCHEMA as RUN_PYTHON_SCHEMA
from tools.code.run_python import run_python
from tools.code.run_tests import SCHEMA as RUN_TESTS_SCHEMA
from tools.code.run_tests import run_tests
from tools.codebase.scan_codebase import SCHEMA as SCAN_CODEBASE_SCHEMA
from tools.codebase.scan_codebase import scan_codebase
from tools.common import fail
from tools.filesystem.apply_patch import SCHEMA as APPLY_PATCH_SCHEMA
from tools.filesystem.apply_patch import apply_patch
from tools.filesystem.delete_file import SCHEMA as DELETE_FILE_SCHEMA
from tools.filesystem.delete_file import delete_file
from tools.filesystem.edit_file import SCHEMA as EDIT_FILE_SCHEMA
from tools.filesystem.edit_file import edit_file
from tools.filesystem.glob import SCHEMA as GLOB_SCHEMA
from tools.filesystem.glob import glob
from tools.filesystem.grep import SCHEMA as GREP_SCHEMA
from tools.filesystem.grep import grep
from tools.filesystem.list_dir import SCHEMA as LIST_DIR_SCHEMA
from tools.filesystem.list_dir import list_dir
from tools.filesystem.move_file import SCHEMA as MOVE_FILE_SCHEMA
from tools.filesystem.move_file import move_file
from tools.filesystem.multi_edit import SCHEMA as MULTI_EDIT_SCHEMA
from tools.filesystem.multi_edit import multi_edit
from tools.filesystem.read_file import SCHEMA as READ_FILE_SCHEMA
from tools.filesystem.read_file import read_file
from tools.filesystem.read_many_files import SCHEMA as READ_MANY_FILES_SCHEMA
from tools.filesystem.read_many_files import read_many_files
from tools.filesystem.write_file import SCHEMA as WRITE_FILE_SCHEMA
from tools.filesystem.write_file import write_file
from tools.git.git_add import SCHEMA as GIT_ADD_SCHEMA
from tools.git.git_add import git_add
from tools.git.git_branch import SCHEMA as GIT_BRANCH_SCHEMA
from tools.git.git_branch import git_branch
from tools.git.git_checkout import SCHEMA as GIT_CHECKOUT_SCHEMA
from tools.git.git_checkout import git_checkout
from tools.git.git_commit import SCHEMA as GIT_COMMIT_SCHEMA
from tools.git.git_commit import git_commit
from tools.git.git_diff import SCHEMA as GIT_DIFF_SCHEMA
from tools.git.git_diff import git_diff
from tools.git.git_log import SCHEMA as GIT_LOG_SCHEMA
from tools.git.git_log import git_log
from tools.git.git_merge import SCHEMA as GIT_MERGE_SCHEMA
from tools.git.git_merge import git_merge
from tools.git.git_pull import SCHEMA as GIT_PULL_SCHEMA
from tools.git.git_pull import git_pull
from tools.git.git_push import SCHEMA as GIT_PUSH_SCHEMA
from tools.git.git_push import git_push
from tools.git.git_status import SCHEMA as GIT_STATUS_SCHEMA
from tools.git.git_status import git_status
from tools.memory.forget import SCHEMA as FORGET_SCHEMA
from tools.memory.forget import forget
from tools.memory.recall import SCHEMA as RECALL_SCHEMA
from tools.memory.recall import recall
from tools.memory.remember import SCHEMA as REMEMBER_SCHEMA
from tools.memory.remember import remember
from tools.personal.cancel_job import SCHEMA as CANCEL_JOB_SCHEMA
from tools.personal.cancel_job import cancel_job
from tools.personal.daemon_status import SCHEMA as DAEMON_STATUS_SCHEMA
from tools.personal.daemon_status import daemon_status
from tools.personal.generate_briefing import SCHEMA as GENERATE_BRIEFING_SCHEMA
from tools.personal.generate_briefing import generate_briefing
from tools.personal.get_jobs import SCHEMA as GET_JOBS_SCHEMA
from tools.personal.get_jobs import get_jobs
from tools.personal.schedule_job import SCHEMA as SCHEDULE_JOB_SCHEMA
from tools.personal.schedule_job import schedule_job
from tools.personal.send_telegram import SCHEMA as SEND_TELEGRAM_SCHEMA
from tools.personal.send_telegram import send_telegram
from tools.personal.user_manager import SCHEMA as USER_MANAGER_SCHEMA
from tools.personal.user_manager import user_manager
from tools.research.deep_research import SCHEMA as DEEP_RESEARCH_SCHEMA
from tools.research.deep_research import deep_research
from tools.research.export_research import SCHEMA as EXPORT_RESEARCH_SCHEMA
from tools.research.export_research import export_research
from tools.research.quick_research import SCHEMA as QUICK_RESEARCH_SCHEMA
from tools.research.quick_research import quick_research
from tools.research.web_scrape import SCHEMA as WEB_SCRAPE_SCHEMA
from tools.research.web_scrape import web_scrape
from tools.research.web_search import SCHEMA as WEB_SEARCH_SCHEMA
from tools.research.web_search import web_search
from tools.shell.bash import SCHEMA as BASH_SCHEMA
from tools.shell.bash import bash
from tools.web.web_fetch import SCHEMA as WEB_FETCH_SCHEMA
from tools.web.web_fetch import web_fetch

ToolFunc = Callable[..., dict[str, Any]]

TOOL_REGISTRY: dict[str, tuple[ToolFunc, dict[str, Any]]] = {
    # filesystem read
    "read_file": (read_file, READ_FILE_SCHEMA),
    "read_many_files": (read_many_files, READ_MANY_FILES_SCHEMA),
    "glob": (glob, GLOB_SCHEMA),
    "grep": (grep, GREP_SCHEMA),
    "list_dir": (list_dir, LIST_DIR_SCHEMA),
    # filesystem write
    "write_file": (write_file, WRITE_FILE_SCHEMA),
    "edit_file": (edit_file, EDIT_FILE_SCHEMA),
    "multi_edit": (multi_edit, MULTI_EDIT_SCHEMA),
    "apply_patch": (apply_patch, APPLY_PATCH_SCHEMA),
    "move_file": (move_file, MOVE_FILE_SCHEMA),
    "delete_file": (delete_file, DELETE_FILE_SCHEMA),
    # shell
    "bash": (bash, BASH_SCHEMA),
    # git
    "git_status": (git_status, GIT_STATUS_SCHEMA),
    "git_diff": (git_diff, GIT_DIFF_SCHEMA),
    "git_log": (git_log, GIT_LOG_SCHEMA),
    "git_branch": (git_branch, GIT_BRANCH_SCHEMA),
    "git_add": (git_add, GIT_ADD_SCHEMA),
    "git_commit": (git_commit, GIT_COMMIT_SCHEMA),
    "git_push": (git_push, GIT_PUSH_SCHEMA),
    "git_pull": (git_pull, GIT_PULL_SCHEMA),
    "git_checkout": (git_checkout, GIT_CHECKOUT_SCHEMA),
    "git_merge": (git_merge, GIT_MERGE_SCHEMA),
    # memory
    "remember": (remember, REMEMBER_SCHEMA),
    "recall": (recall, RECALL_SCHEMA),
    "forget": (forget, FORGET_SCHEMA),
    # agent
    "task": (task, TASK_SCHEMA),
    "ask": (ask, ASK_SCHEMA),
    "skill": (skill, SKILL_SCHEMA),
    "todo_write": (todo_write, TODO_WRITE_SCHEMA),
    # codebase
    "scan_codebase": (scan_codebase, SCAN_CODEBASE_SCHEMA),
    # code execution
    "run_python": (run_python, RUN_PYTHON_SCHEMA),
    "lint_python": (lint_python, LINT_PYTHON_SCHEMA),
    "run_tests": (run_tests, RUN_TESTS_SCHEMA),
    # web
    "web_fetch": (web_fetch, WEB_FETCH_SCHEMA),
    "web_scrape": (web_scrape, WEB_SCRAPE_SCHEMA),
    # research
    "web_search": (web_search, WEB_SEARCH_SCHEMA),
    "quick_research": (quick_research, QUICK_RESEARCH_SCHEMA),
    "deep_research": (deep_research, DEEP_RESEARCH_SCHEMA),
    "export_research": (export_research, EXPORT_RESEARCH_SCHEMA),
    # personal
    "send_telegram": (send_telegram, SEND_TELEGRAM_SCHEMA),
    "schedule_job": (schedule_job, SCHEDULE_JOB_SCHEMA),
    "cancel_job": (cancel_job, CANCEL_JOB_SCHEMA),
    "get_jobs": (get_jobs, GET_JOBS_SCHEMA),
    "daemon_status": (daemon_status, DAEMON_STATUS_SCHEMA),
    "user_manager": (user_manager, USER_MANAGER_SCHEMA),
    "generate_briefing": (generate_briefing, GENERATE_BRIEFING_SCHEMA),
}

# Fail-fast: registry dan permission harus 1:1. Kalau tidak sama,
# ada tool yang lupa didaftarkan di salah satu sisi.
_missing_in_registry = set(KNOWN_TOOLS) - set(TOOL_REGISTRY)
_missing_in_permissions = set(TOOL_REGISTRY) - set(KNOWN_TOOLS)
if _missing_in_registry or _missing_in_permissions:
    raise RuntimeError(
        f"Registry ↔ permissions tidak sinkron: "
        f"kurang di registry={sorted(_missing_in_registry)}, "
        f"kurang di permissions={sorted(_missing_in_permissions)}"
    )


def get_tool_definitions() -> list[dict[str, Any]]:
    """Daftar tool dalam format JSON Schema (OpenAI function calling) buat LLM."""
    return [schema for _, schema in TOOL_REGISTRY.values()]


# ── Runtime registration buat plugin (Phase 5 Step 2) ──
# Dipanggil core/plugin_loader saat startup. Tool plugin hidup di
# TOOL_REGISTRY yang sama → execute_tool + get_tool_definitions langsung
# bisa pakai tanpa perubahan. Nama tabrakan dengan builtin → ditolak
# (return False) supaya plugin tidak bisa bajak tool inti.
_PLUGIN_TOOLS: set[str] = set()


def register_tool(name: str, func: ToolFunc, schema: dict[str, Any]) -> bool:
    """Daftarkan tool runtime. False kalau nama sudah ada / schema invalid."""
    if not name or name in TOOL_REGISTRY:
        return False
    try:
        fname = schema["function"]["name"]
    except (KeyError, TypeError):
        return False
    if fname != name:
        return False
    TOOL_REGISTRY[name] = (func, schema)
    _PLUGIN_TOOLS.add(name)
    return True


def unregister_tool(name: str) -> None:
    """Cabut tool plugin (buat test / reload). Builtin tidak bisa dicabut."""
    if name in _PLUGIN_TOOLS:
        TOOL_REGISTRY.pop(name, None)
        _PLUGIN_TOOLS.discard(name)


def plugin_tool_names() -> list[str]:
    """Nama tool plugin yang sedang terdaftar."""
    return sorted(_PLUGIN_TOOLS)


def _supports_output(func: ToolFunc) -> set[str]:
    """Nama param yang didukung func (inspect aman, gagal → set kosong)."""
    try:
        return set(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        return set()


def is_plugin_tool(name: str) -> bool:
    """True kalau tool berasal dari plugin (bukan builtin)."""
    return name in _PLUGIN_TOOLS


def execute_tool(name: str, params: dict[str, Any] | None = None,
                 on_output: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Jalankan tool by name. Selalu return dict {success, result, error}.

    `on_output` (live stream per baris) diteruskan HANYA ke tool yang
    mendeklarasikan param itu (run_python/run_tests/bash) — tool lain
    tak tersentuh, schema LLM tak berubah.
    """
    entry = TOOL_REGISTRY.get(name)
    if entry is None:
        return fail(f"Tool tidak dikenal: {name}")
    func, _ = entry
    kwargs = dict(params or {})
    if on_output is not None and "on_output" in _supports_output(func):
        kwargs["on_output"] = on_output
    try:
        return func(**kwargs)
    except TypeError as e:
        # Bedakan salah-param (signature) vs bug di dalam body tool:
        # TypeError signature terjadi di frame pemanggil saja (1 frame);
        # TypeError dari body tool membawa frame tool juga (≥2 frame).
        tb = traceback.extract_tb(e.__traceback__)
        if len(tb) <= 1:
            return fail(f"Parameter salah untuk `{name}`: {e}")
        return fail(f"Tool `{name}` crash ({type(e).__name__}): {e}")
    except Exception as e:
        return fail(f"Tool `{name}` crash ({type(e).__name__}): {e}")


if __name__ == "__main__":
    import os
    import tempfile

    # Isolasikan home agar test tidak menyentuh data asli user.
    tmp_home = tempfile.mkdtemp(prefix="multacd-test-")
    os.environ["MULTACD_HOME"] = tmp_home

    defs = get_tool_definitions()
    assert len(defs) == len(KNOWN_TOOLS) == 46, len(defs)
    for d in defs:
        assert d["type"] == "function" and d["function"]["name"], d

    # Routing + format konsisten
    r = execute_tool("bash", {"command": "echo hi"})
    assert r == {"success": True, "result": "hi", "error": None}, r
    r = execute_tool("tidak_ada", {})
    assert not r["success"] and "tidak dikenal" in r["error"], r
    r = execute_tool("read_file", {"salah": 1})
    assert not r["success"] and "Parameter" in r["error"], r

    # Memory roundtrip (isolated home)
    assert execute_tool("remember", {"key": "nama", "value": "budi"})["success"]
    assert execute_tool("recall", {"key": "nama"})["result"] == "budi"
    assert execute_tool("recall", {})["result"] == {"nama": "budi"}
    assert execute_tool("forget", {"key": "nama"})["success"]
    assert not execute_tool("recall", {"key": "nama"})["success"]

    # Skill roundtrip (isolated home)
    assert execute_tool("skill", {"action": "save", "name": "py", "content": "# python"})["success"]
    assert execute_tool("skill", {"action": "load", "name": "py"})["result"] == "# python"
    assert execute_tool("skill", {"action": "list"})["result"] == ["py"]

    # todo_write
    r = execute_tool("todo_write", {"todos": [{"content": "a", "status": "done"}], "workdir": tmp_home})
    assert r["success"], r

    print(f"✅ registry self-test OK ({len(defs)} tools, sinkron dengan permissions)")
