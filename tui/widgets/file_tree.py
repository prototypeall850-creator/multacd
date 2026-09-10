"""File tree — panel kiri project (toggle Ctrl+T).

Root di workdir sesi. Filter selaras core/codebase.py: hidden, SKIP_DIRS
(.venv, plan/, roadmap/, ...), *.pyc, secrets, file planning.
Enter/klik file → FileOpenRequested(path) ke MainScreen (auto-baca).
File modified (git) ditandai ● kuning via mark_modified().
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.text import Text
from textual.message import Message
from textual.widgets import DirectoryTree
from textual.widgets._tree import TreeNode

from core.codebase import SKIP_DIRS


class FileOpenRequested(Message):
    """User pilih file di tree → MainScreen auto-jalankan turn baca file."""

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path


def modified_files(workdir: Path | str) -> set[str]:
    """Set path relatif file modified/untracked (git porcelain)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(workdir), "status", "--porcelain", "--", "."],
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return set()
    if proc.returncode != 0:
        return set()
    out: set[str] = set()
    for line in proc.stdout.splitlines():
        name = line[3:].strip().strip('"')
        if " -> " in name:  # rename: "lama -> baru"
            name = name.split(" -> ", 1)[1]
        if name:
            out.add(name)
    return out


class ProjectTree(DirectoryTree):
    """DirectoryTree terfilter + marker modified."""

    def __init__(self, workdir: Path | str) -> None:
        super().__init__(str(workdir), id="file-tree")
        self._workdir = Path(workdir)
        self._modified: set[str] = set()

    def filter_paths(self, paths):  # type: ignore[override]
        kept = []
        for p in paths:
            name = p.name
            if name.startswith("."):
                continue
            if p.is_dir():
                if name in SKIP_DIRS:
                    continue
            else:
                if name in SKIP_DIRS or name.endswith(".pyc"):
                    continue
                if name == ".env" or name.endswith((".key", ".pem")):
                    continue
                upper = name.upper()
                if upper == "PLAN.MD" or upper.startswith(("PLAN-", "PLAN_")):
                    continue
                if upper == "ROADMAP.MD" or upper.startswith(("ROADMAP-", "ROADMAP_")):
                    continue
                if name == "soul.md":
                    continue
            kept.append(p)
        return kept

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.post_message(FileOpenRequested(str(event.path)))

    def mark_modified(self, modified: set[str]) -> None:
        """Tandai file modified dengan ● (dipanggil saat tree ditampilkan)."""
        self._modified = modified
        try:
            nodes = list(self.walk_children())
        except Exception:
            return
        for node in nodes:
            if not isinstance(node, TreeNode):
                continue
            data = node.data
            path = getattr(data, "path", None)
            if path is None or Path(path).is_dir():
                continue
            try:
                rel = str(Path(path).relative_to(self._workdir))
            except ValueError:
                continue
            label = Path(path).name
            if rel in modified:
                node.set_label(Text(f"{label} ●", style="yellow"))
            else:
                node.set_label(label)
