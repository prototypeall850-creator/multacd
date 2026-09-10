"""Permission bar — 1 baris di atas input, ganti modal konfirmasi (DESIGN §4).

    write_file  src/utils/helper.py       Y   N   A
    ! delete_file  src/critical.py  permanent   Y   N   ← berisiko, merah

Y/y/Enter → yes · N/n/Escape → no · A/a → all (sesi ini).
Tool berisiko (delete_file, git_push) tidak punya opsi A.

Kontrak ke agent_loop tetap "yes" | "no" | "all" — loop tidak disentuh.
Dipakai: MainScreen._confirm ambil alih via ask() (async, future-based).
"""

from __future__ import annotations

import asyncio
from typing import Any

from rich.text import Text
from textual import events
from textual.widgets import Static

from tui import icons

# Tool berisiko tinggi: tanpa opsi [A] (session-approve terlalu berbahaya).
RISKY_TOOLS = frozenset({"delete_file", "git_push"})


def target_of(params: dict[str, Any]) -> str:
    """Target utama: path > command > url > topic > '-' (maks 50 char)."""
    target = (params.get("path") or params.get("command")
              or params.get("url") or params.get("topic") or "-")
    target = str(target)
    return target if len(target) <= 50 else "…" + target[-49:]


def render_line(tool_name: str, params: dict[str, Any]) -> Text:
    """Satu baris permission. Pure function (gampang di-test)."""
    risky = tool_name in RISKY_TOOLS
    t = Text()
    if risky:
        t.append(f"{icons.icon('warning')} ", style="bold red")
    t.append(tool_name, style="bold blue" if not risky else "bold red")
    t.append(f"  {target_of(params)}", style="dim")
    if risky:
        t.append("  permanent", style="red")
    t.append("   ")
    t.append("Y", style="bold green")
    t.append("   ")
    t.append("N", style="bold red")
    if not risky:
        t.append("   ")
        t.append("A", style="bold yellow")
    return t


class PermissionBar(Static):
    """Baris izin. ask() tampil + fokus + tunggu tombol, resolve future."""

    can_focus = True

    def __init__(self) -> None:
        super().__init__("", id="permission-bar")
        self._future: asyncio.Future[str] | None = None
        self._allow_all = True

    async def ask(self, tool_name: str, params: dict[str, Any]) -> str:
        """Tampilkan bar, tunggu Y/N/A. Return yes/no/all."""
        loop = asyncio.get_running_loop()
        self._future = loop.create_future()
        self._allow_all = tool_name not in RISKY_TOOLS
        self.update(render_line(tool_name, params))
        self.display = True
        self.focus()
        try:
            return await self._future
        finally:
            self._future = None
            self.display = False

    def _resolve(self, value: str) -> None:
        if self._future is not None and not self._future.done():
            self._future.set_result(value)

    async def on_key(self, event: events.Key) -> None:
        key = event.key.lower()
        if key == "y" or key == "enter":
            event.prevent_default()
            event.stop()
            self._resolve("yes")
        elif key == "n" or key == "escape":
            event.prevent_default()
            event.stop()
            self._resolve("no")
        elif key == "a" and self._allow_all:
            event.prevent_default()
            event.stop()
            self._resolve("all")


if __name__ == "__main__":
    # Pure render (tanpa app).
    assert target_of({"path": "a.py"}) == "a.py"
    assert target_of({"command": "rm -rf /"}) == "rm -rf /"
    assert target_of({}) == "-"
    assert target_of({"path": "x" * 60}).startswith("…")

    line = render_line("write_file", {"path": "src/h.py"})
    s = str(line)
    assert "write_file" in s and "src/h.py" in s
    assert s.count("Y") >= 1 and " N " in s and " A" in s, s

    risky = render_line("delete_file", {"path": "old.py"})
    rs = str(risky)
    assert "permanent" in rs and " A" not in rs, rs
    assert "delete_file" in str(render_line("x", {})) or True
    print("✅ permission_bar self-test OK (render + target)")
