"""Permission popup — panel izin di atas input (#4 v2: aksi kontekstual).

Tombol pendek (muat 40 kolom Termux):

    write_file  src/utils/helper.py
    [ Yes (Y) ]  [ No (N) ]  [ All (A) ]

    git_commit  "feat: x"           [diff preview otomatis di chat]
    [ Yes (Y) ]  [ Edit (E) ]  [ No (N) ]  [ All (A) ]

    ! git_push  main (protected)    [tanpa All — RISKY]
    [ Yes (Y) ]  [ Branch (B) ]  [ No (N) ]

Kontrak ke agent_loop: "yes" | "no" | "all" | "edit:<pesan>" | "branch".
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from core.permissions import NO_SESSION_APPROVAL, RISKY_TOOLS  # single source of truth
from tui import icons
from tui.markup_safe import tx_escape as escape


def target_of(params: dict[str, Any]) -> str:
    """Target utama: path > command > url > topic > '-' (maks 50 char)."""
    target = (params.get("path") or params.get("command")
              or params.get("url") or params.get("topic") or "-")
    target = str(target)
    return target if len(target) <= 50 else "…" + target[-49:]


def prompt_of(tool_name: str, params: dict[str, Any]) -> str:
    """Baris prompt (markup). Nilai dinamis di-escape (issue #29). Pure function."""
    risky = tool_name in RISKY_TOOLS
    pre = f"[bold red]{icons.icon('warning')} [/]" if risky else ""
    name_style = "bold red" if risky else "bold cyan"
    name = escape(tool_name)
    if tool_name == "git_commit":  # #4: pesan commit ikut tampil
        first = str(params.get("message", "")).strip().splitlines()
        msg = escape(first[0][:60] if first else "(tanpa pesan)")
        return f"[{name_style}]{name}[/]  [dim]\"{msg}\"[/]"
    if tool_name == "git_push":  # #4: target branch ikut tampil
        br = escape(str(params.get("branch", "") or "(aktif)"))
        prot = "  [red](protected)[/]" if _is_protected_push(params) else ""
        return f"{pre}[{name_style}]{name}[/]  [dim]{br}[/]{prot}"
    post = "  [red]permanent[/]" if risky else ""
    return f"{pre}[{name_style}]{name}[/]  [dim]{escape(target_of(params))}[/]{post}"


def _is_protected_push(params: dict[str, Any]) -> bool:
    """True kalau push ini menyasar branch dilindungi (tanpa opt-in).

    Baca git lokal (cepat, tanpa network). Gagal resolve → False
    (tombol Branch diputuskan ask() via checker yang ask duluan).
    """
    if params.get("allow_protected"):
        return False
    try:
        from tools.git.git_push import PROTECTED_BRANCHES, _current_branch
    except Exception:
        return False
    target = str(params.get("branch", "")).strip()
    if not target:
        try:
            target = _current_branch(str(params.get("workdir", "."))) or ""
        except Exception:
            return False
    return target in PROTECTED_BRANCHES


class PermissionPopup(Vertical):
    """Panel izin + tombol. ask() tampil + fokus + tunggu, resolve future."""

    can_focus = False

    def __init__(self) -> None:
        super().__init__(id="permission-popup")
        self._future: asyncio.Future[str] | None = None
        self._allow_all = True
        self._extra = ""  # "" | "edit" (git_commit) | "branch" (git_push)

    def compose(self) -> ComposeResult:
        yield Static("", id="perm-prompt")
        with Horizontal(id="perm-buttons"):
            yield Button("Yes (Y)", id="perm-yes", variant="success")
            yield Button("Edit (E)", id="perm-extra-edit", variant="primary")
            yield Button("Branch (B)", id="perm-extra-branch", variant="primary")
            yield Button("No (N)", id="perm-no", variant="error")
            yield Button("All (A)", id="perm-all", variant="warning")

    async def ask(self, tool_name: str, params: dict[str, Any]) -> str:
        """Tampilkan popup, tunggu tombol/keyboard.

        Return yes/no/all/edit:<pesan>/branch.
        """
        loop = asyncio.get_running_loop()
        self._future = loop.create_future()
        # [A] disembunyikan untuk tool yang kontraknya tidak boleh session-
        # approve (eksekusi kode, research, risky) — bukan cuma risky,
        # biar tombolnya tidak jadi janji palsu (klik [A] tapi tak persist).
        self._allow_all = tool_name not in NO_SESSION_APPROVAL
        # #4: aksi kontekstual — Edit pesan (commit) / Branch baru (push).
        if tool_name == "git_commit":
            self._extra = "edit"
        elif tool_name == "git_push" and _is_protected_push(params):
            self._extra = "branch"
        else:
            self._extra = ""
        self.query_one("#perm-prompt", Static).update(
            prompt_of(tool_name, params))
        self.query_one("#perm-all", Button).display = self._allow_all
        self.query_one("#perm-extra-edit", Button).display = self._extra == "edit"
        self.query_one("#perm-extra-branch", Button).display = self._extra == "branch"
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
        """Rute Y/N/A/E/B/Enter/Esc/arrows. True kalau dikonsumsi."""
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
        if key == "e" and self._extra == "edit":
            self._resolve("edit:")
            return True
        if key == "b" and self._extra == "branch":
            self._resolve("branch")
            return True
        if key in ("left", "right"):
            self._cycle(key == "right")
            return True
        return False

    def _cycle(self, forward: bool) -> None:
        """Pindah fokus antar tombol yang kelihatan (arrow)."""
        try:
            btns = [b for b in self.query(Button)
                    if b.id in ("perm-yes", "perm-no", "perm-all",
                                "perm-extra-edit", "perm-extra-branch")
                    and b.display]
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
                        "perm-all": "all", "perm-extra-edit": "edit:",
                        "perm-extra-branch": "branch"}[event.button.id])

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
    c = prompt_of("git_commit", {"message": "feat: tambah x"})
    assert "git_commit" in c and "feat: tambah x" in c
    p = prompt_of("git_push", {"branch": "main"})
    assert "git_push" in p and "main" in p and "protected" in p
    p2 = prompt_of("git_push", {"branch": "fitur"})
    assert "protected" not in p2

    from tui.widgets.permission_popup import PermissionPopup as _PP

    bar = _PP.__new__(_PP)
    bar._future = None
    bar._allow_all = True
    bar._extra = ""
    assert bar.answer_key("y") and bar.answer_key("n")
    assert bar.answer_key("a") and bar.answer_key("left")
    assert not bar.answer_key("z")
    assert not bar.answer_key("e") and not bar.answer_key("b")
    bar._allow_all = False
    assert not bar.answer_key("a")
    bar._extra = "edit"
    assert bar.answer_key("e")
    bar._extra = "branch"
    assert bar.answer_key("b")
    # #29: target/pesan berisi bracket → prompt tetap valid markup.
    from textual.content import Content as _Content
    nasty: dict[str, Any] = {"command": 'ls [a-z]* [x=y="list_dir", z]'}
    _Content.from_markup(prompt_of("bash", nasty))
    _Content.from_markup(prompt_of(
        "git_commit", {"message": 'feat: [x=y="a", b] ok'}))
    print("✅ permission_popup self-test OK (prompt + keys + extra + markup)")
