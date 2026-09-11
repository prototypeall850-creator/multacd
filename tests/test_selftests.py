"""Regression suite: jalankan self-test bawaan tiap modul via subprocess.

Setiap modul inti punya blok `if __name__ == "__main__"` berisi assert
(pola self-test project ini). Test ini memastikan semuanya tetap hijau
tanpa perlu refactor — jadi `run_tests` punya sesuatu untuk di-collect.

Isolasi: semua subprocess dapat MULTACD_HOME menunjuk folder sementara,
jadi memory/skill/config tidak menyentuh data asli user.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Home terisolasi untuk semua subprocess test (dibuat sekali per sesi).
_ISOLATED_HOME = tempfile.mkdtemp(prefix="multacd-pytest-home-")

# Modul dengan self-test `python -m <module>` (exit 0 = lolos).
SELF_TEST_MODULES = [
    "core.agent_loop",
    "core.llm_client",
    "core.permissions",
    "core.mode_manager",
    "core.codebase",
    "core.prompt_composer",
    "memory.context",
    "tools.registry",
    "tools.code.run_python",
    "tools.code.lint_python",
    "tools.code.run_tests",
    "tools.git.git_merge",
    "tools.git.git_push",
    "tui.widgets.diff_viewer",
    "tools.research.web_scrape",
    "tools.research.web_search",
    "core.research.query_generator",
    "core.research.orchestrator",
    "core.research.bus",
    "tools.research.quick_research",
    "tools.research.deep_research",
    "tools.research.export_research",
    "tui.icons",
    "tui.themes",
    "tui.widgets.thinking_bar",
    "tui.widgets.permission_popup",
    "tui.widgets.tool_activity",
    "tui.widgets.slash_palette",
    "tui.screens.setup_wizard",
    "search_providers.base",
    "search_providers.tavily",
    "search_providers.exa",
    "search_providers.brave",
    "search_providers.serpapi",
    "search_providers.duckduckgo",
    "search_providers",
    "briefing.privacy",
    "tg.access_control",
    "tg.formatter",
    "tg.agent",
    "tg.file_handler",
    "tg.handlers",
    "tg.bot",
    "tools.personal.send_telegram",
    "tools.personal.schedule_job",
    "tools.personal.cancel_job",
    "tools.personal.get_jobs",
    "tools.personal.daemon_status",
    "scheduler.engine",
    "scheduler.jobs.briefing_job",
    "scheduler.jobs.research_job",
    "briefing.sources.todo_source",
    "briefing.sources.git_source",
    "briefing.sources.news_source",
    "briefing.generator",
]


@pytest.mark.parametrize("module", SELF_TEST_MODULES)
def test_module_selftest(module: str) -> None:
    """Self-test `python -m <module>` harus exit 0."""
    env = {**os.environ, "MULTACD_HOME": _ISOLATED_HOME}
    proc = subprocess.run(
        [sys.executable, "-m", module],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=180, env=env,
    )
    assert proc.returncode == 0, (
        f"{module} gagal:\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )


def test_config_respects_multacd_home() -> None:
    """Regression: core/config.py harus hormati MULTACD_HOME (isolation test).

    Dulu CONFIG_DIR hardcode Path.home() → test bisa baca config/API key asli.
    """
    env = {**os.environ, "MULTACD_HOME": _ISOLATED_HOME}
    proc = subprocess.run(
        [sys.executable, "-c", "from core.config import CONFIG_DIR; print(CONFIG_DIR)"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert _ISOLATED_HOME in proc.stdout, proc.stdout
