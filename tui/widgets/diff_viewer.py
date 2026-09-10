"""Diff viewer — tampilkan git diff dengan highlight (toggle Ctrl+D).

Merah = baris hapus, hijau = baris tambah, cyan = hunk header.
Dipanggil manual (toggle) dan dari flow commit (Step 9 wiring penuh).
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.widgets import Static

from tools.git.git_diff import git_diff


class DiffViewer(Static):
    """Panel diff; hidden default, isi via refresh()."""

    def __init__(self) -> None:
        super().__init__("", id="diff-viewer")
        self._workdir = "."

    def refresh_diff(self, workdir: Path | str = ".") -> None:
        self._workdir = str(workdir)
        result = git_diff(workdir=str(workdir))
        if not result["success"]:
            self.update(Text(f"(diff gagal: {result['error']})", style="red"))
            return
        self.update(render_diff(result["result"]))


def render_diff(diff_text: str) -> Text:
    """Warnai unified diff. Pure function (gampang di-test)."""
    t = Text()
    if not diff_text.strip() or diff_text.strip() == "(tidak ada output)":
        return Text("(bersih, tidak ada perubahan)", style="dim")
    for line in diff_text.splitlines():
        if line.startswith(("+++", "---")):
            t.append(line + "\n", style="dim")
        elif line.startswith("+"):
            t.append(line + "\n", style="green")
        elif line.startswith("-"):
            t.append(line + "\n", style="red")
        elif line.startswith("@@"):
            t.append(line + "\n", style="cyan")
        elif line.startswith("diff --git"):
            t.append(line + "\n", style="bold yellow")
        else:
            t.append(line + "\n", style="dim")
    return t


if __name__ == "__main__":
    sample = ("diff --git a/x.py b/x.py\n"
              "@@ -1,2 +1,2 @@\n"
              "-lama\n"
              "+baru\n"
              " konteks\n")
    out = render_diff(sample)
    assert str(out).count("\n") == 5, repr(str(out))
    assert "bersih" in str(render_diff(""))
    assert "bersih" in str(render_diff("(tidak ada output)"))
    # +++ / --- header tetap dim, bukan hijau/merah
    spans = {(s.start, s.end, s.style) for s in out._spans}
    assert any("green" in str(s) for s in out._spans), "baris + harus hijau"
    assert any("red" in str(s) for s in out._spans), "baris - harus merah"
    print("✅ diff_viewer self-test OK (render + edge)")
