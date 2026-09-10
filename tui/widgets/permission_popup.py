"""Permission popup — panel izin di atas input (ganti permission 1-baris).

Kenapa tombol beneran: routing key ke baris statis rapuh (tergantung
fokus widget — lihat issue #19). Tombol bisa diklik mouse, difokus
Tab/arrow, DAN tetap respons Y/N/A:

    write_file  src/utils/helper.py
    [ Allow (Y) ]  [ Deny (N) ]  [ All (A) ]

    ! delete_file  src/old.py  permanent (merah, tanpa tombol All)

Kontrak ke agent_loop tetap "yes" | "no" | "all".
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from tui import icons

# Tool berisiko tinggi: tanpa opsi [A] (session-approve terlalu berbahaya).
RISKY_TOOLS = frozenset({"delete_file", "git_push"})


def target_of(params: dict[str, Any]) -> str:
    """Target utama: path > command > url > topic > '-' (maks 50 char)."""
    target = (params.get("path") or params.get("command")
              or params.get("url") or params.get("topic") or "-")
    target = str(target)
    return target if len(target) <= 50 else "…" + target[-49:]


def prompt_of(tool_name: str, params: dict[str, Any]) -> str:
    """Baris prompt (markup). Pure function."""
    risky = tool_name in RISKY_TOOLS
    pre = f"[bold red]{icons.icon('warning')} [/]" if risky else ""
    name_style = "bold red" if risky else "bold blue"
    post = "  [red]permanent[/]" if risky else ""
    return f"{pre}[{name_style}]{tool_name}[/]  [dim]{target_of(params)}[/]{post}"


class PermissionPopup(Vertical):
    """Panel izin + 3 tombol. ask() tampil + fokus + tunggu, resolve future."""

    can_focus = False

    def __init__(self) -> None:
        super().__init__(id="permission-popup")
        self._future: asyncio.Future[str] | None = None
        self._allow_all = True

    def compose(self) -> ComposeResult:
        yield Static("", id="perm-prompt")
        with Horizontal(id="perm-buttons"):
            yield Button("Allow (Y)", id="perm-yes", variant="success")
            yield Button("Deny (N)", id="perm-no", variant="error")
            yield Button("All (A)", id="perm-all", variant="warning")

    async def ask(self, tool_name: str, params: dict[str, Any]) -> str:
        """Tampilkan popup, tunggu tombol/keyboard. Return yes/no/all."""
        loop = asyncio.get_running_loop()
        self._future = loop.create_future()
        self._allow_all = tool_name not in RISKY_TOOLS
        self.query_one("#perm-prompt", Static).update(
            prompt_of(tool_name, params))
        self.query_one("#perm-all", Button).display = self._allow_all
        self.display = True
        self.query_one("#perm-yes", Button).focus()
        try:
            return await self._future
        finally:
            self._future = None
            self.display = False
            # Kembalikan fokus ke input (kalau user tadi panah/klik tombol,
            # fokus bisa nyangkut di tombol yang kini hidden).
            with suppress(Exception):
                from tui.widgets.input_bar import InputBar
                self.screen.query_one(InputBar).focus()

    @property
    def is_waiting(self) -> bool:
        """True saat popup tampil dan menunggu jawaban."""
        return bool(self.display) and self._future is not None \
            and not self._future.done()

    def _resolve(self, value: str) -> None:
        if self._future is not None and not self._future.done():
            self._future.set_result(value)

    def answer_key(self, key: str) -> bool:
        """Rute Y/N/A/Enter/Esc/arrows. True kalau dikonsumsi."""
        key = key.lower()
        if key == "y":
            self._resolve("yes")
            return True
        if key == "n" or key == "escape":
            self._resolve("no")
            return True
        if key == "a" and self._allow_all:
            self._resolve("all")
            return True
        if key in ("left", "right"):
            self._cycle(key == "right")
            return True
        return False

    def _cycle(self, forward: bool) -> None:
        """Pindah fokus antar tombol yang kelihatan (arrow)."""
        try:
            btns = [b for b in self.query(Button)
                    if b.id in ("perm-yes", "perm-no", "perm-all") and b.display]
        except Exception:
            return
        if not btns:
            return
        try:
            focused = self.app.focused
        except Exception:
            focused = None
        try:
            idx = btns.index(focused) if focused in btns else -1
        except ValueError:
            idx = -1
        btns[(idx + (1 if forward else -1)) % len(btns)].focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        self._resolve({"perm-yes": "yes", "perm-no": "no",
                       "perm-all": "all"}[event.button.id])

    async def on_key(self, event: events.Key) -> None:
        # Enter di tombol = klik native (jangan dobel-resolve ke yes —
        # _resolve guard future, tapi cegah bubble liar sekalian).
        try:
            on_button = isinstance(self.app.focused, Button)
        except Exception:
            on_button = False
        if event.key == "enter" and on_button:
            return
        if self.answer_key(event.key):
            event.prevent_default()
            event.stop()


if __name__ == "__main__":
    assert target_of({"path": "a.py"}) == "a.py"
    assert target_of({"command": "rm -rf /"}) == "rm -rf /"
    assert target_of({}) == "-"
    assert target_of({"path": "x" * 60}).startswith("…")
    s = prompt_of("write_file", {"path": "src/h.py"})
    assert "write_file" in s and "src/h.py" in s and "Allow" not in s
    r = prompt_of("delete_file", {"path": "old.py"})
    assert "permanent" in r

    from tui.widgets.permission_popup import PermissionPopup as _PP

    bar = _PP.__new__(_PP)
    bar._future = None
    bar._allow_all = True
    assert bar.answer_key("y") and bar.answer_key("n")
    assert bar.answer_key("a") and bar.answer_key("left")
    assert not bar.answer_key("z")
    bar._allow_all = False
    assert not bar.answer_key("a")
    print("✅ permission_popup self-test OK (prompt + keys)")
