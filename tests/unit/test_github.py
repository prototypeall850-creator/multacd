"""Guard repo files (Phase 5 Step 8) — template + lisensi ada."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def test_github_templates():
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.md").is_file()
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.md").is_file()
    assert (ROOT / ".github" / "pull_request_template.md").is_file()
    bug = (ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.md").read_text()
    assert "Environment" in bug and "multacd version" in bug


def test_license_mit():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in text and "WITHOUT WARRANTY" in text
