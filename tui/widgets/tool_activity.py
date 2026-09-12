"""Tool activity — baris tool collapsible di chat (DESIGN §5).

Collapsed (default, 1 baris):
    > write_file  src/utils/helper.py                [+]
Expanded (klik header / Enter saat fokus):
    v write_file  src/utils/helper.py                [-]
      Created file (47 lines)
      ──────────────
      + def load_config...

Thinking-expandable dilewati: stream LLM kita tidak membawa reasoning
terpisah (hanya tampil kalau provider support — belum ada yang support).
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual import events
from textual.containers import Vertical
from textual.widgets import Static

from tui import icons
from tui.markup_safe import tx_escape as escape

MAX_DETAIL_CHARS = 1500
MAX_DETAIL_LINES = 20


def target_of(params: dict[str, Any]) -> str:
    target = (params.get("path") or params.get("command")
              or params.get("url") or params.get("topic")
              or params.get("query") or "")
    target = str(target)
    return target if len(target) <= 60 else "…" + target[-59:]


def summarize(result: dict[str, Any] | None) -> tuple[str, str]:
    """(ringkasan 1 baris, detail multi-baris). Pure function."""
    if not result:
        return ("", "")
    if not result.get("success"):
        err = str(result.get("error") or "gagal")
        return (err.splitlines()[0][:100] if err else "gagal", err)
    body = result.get("result")
    if isinstance(body, dict):
        # Hasil terstruktur (research dkk): tampilkan kunci + nilai pendek.
        lines = []
        for k, v in body.items():
            vs = str(v)
            if len(vs) > 200:
                vs = vs[:200] + "…"
            lines.append(f"{k}: {vs}")
        detail = "\n".join(lines)
    else:
        detail = str(body if body is not None else "")
    if not detail.strip():
        return ("ok", "")
    first = detail.strip().splitlines()[0][:100]
    return (first, detail)


def truncate_detail(detail: str) -> str:
    lines = detail.splitlines()[:MAX_DETAIL_LINES]
    text = "\n".join(lines)
    if len(text) > MAX_DETAIL_CHARS:
        text = text[:MAX_DETAIL_CHARS] + "\n…(dipotong)"
    elif len(detail.splitlines()) > MAX_DETAIL_LINES:
        text += "\n…(dipotong)"
    return text


def head_markup(name: str, target: str, done: bool, success: bool) -> str:
    """Header 1 baris (markup). Pure function — gampang dites.

    Nama/target di-escape: path/command user bisa berisi `[...]` yang
    bikin Textual MarkupError kalau mentah (issue #29).
    """
    mark = icons.icon("expand")
    name, target = escape(name), escape(target)
    if not done:
        status = f" [blue]{icons.icon('pending')}[/]"
        return (f"[blue]{icons.icon('running')} {name}[/]"
                f"  [dim]{target}[/]{status}  {mark}")
    if success:
        status = f" [green]{icons.icon('success')}[/]"
        return (f"[green]{name}[/]  [dim]{target}[/]{status}  {mark}")
    status = f" [red]{icons.icon('error')}[/]"
    return (f"[red]{name}[/]  [dim]{target}[/]{status}  {mark}")


def body_text(summary: str, detail: str) -> Text:
    """Body expanded sebagai Rich Text (hasil tool mentah, tanpa markup)."""
    body = summary
    if detail:
        body += "\n─────\n" + truncate_detail(detail)
    return Text(body or "(tidak ada detail)")


class ToolActivity(Vertical):
    """Satu tool call: header (klik/Enter) + body detail (hidden default)."""

    def __init__(self, call_id: str, name: str, params: dict[str, Any]) -> None:
        super().__init__(id=f"tool-{call_id}")
        self._call_id = call_id
        self._name = name
        self._target = target_of(params)
        self._collapsed = True
        self._done = False
        self._success = False
        self._summary = ""
        self._detail = ""
        self._head = Static("", id=f"tool-head-{call_id}")
        self._head.can_focus = True
        self._body = Static("", id=f"tool-body-{call_id}")
        self._body.display = False

    def compose(self):
        yield self._head
        yield self._body

    def on_mount(self) -> None:
        self._paint()

    def set_done(self, success: bool, result: dict[str, Any] | None) -> None:
        self._done = True
        self._success = success
        self._summary, self._detail = summarize(result)
        self._paint()

    def toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._paint()

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.toggle()
        self._head.focus()

    async def on_key(self, event: events.Key) -> None:
        if event.key == "enter" and self._head.has_focus:
            event.prevent_default()
            event.stop()
            self.toggle()

    def _paint(self) -> None:
        if self._collapsed:
            try:
                self._head.update(head_markup(
                    self._name, self._target, self._done, self._success))
                self._body.display = False
            except Exception:
                pass
        else:
            try:
                self._head.update(
                    f"v {escape(self._name)}  {escape(self._target)}  "
                    f"{icons.icon('collapse')}")
                self._body.update(body_text(self._summary, self._detail))
                self._body.display = True
            except Exception:
                pass


if __name__ == "__main__":
    from textual.content import Content as _Content

    assert target_of({"path": "a.py"}) == "a.py"
    assert target_of({}) == ""
    s, d = summarize({"success": True, "result": "Created (3)\nok", "error": None})
    assert s == "Created (3)" and "ok" in d, (s, d)
    s, d = summarize({"success": False, "result": None, "error": "boom\ntrace"})
    assert s == "boom" and "trace" in d
    s, d = summarize({"success": True, "result": {"answer": "x" * 300}, "error": None})
    assert "answer:" in d and d.count("…") == 1
    s, d = summarize(None)
    assert (s, d) == ("", "")
    t = truncate_detail("\n".join(f"l{i}" for i in range(30)))
    assert len(t.splitlines()) == 21 and t.endswith("(dipotong)"), t[-20:]
    # #29: nama/target berisi bracket → header tetap valid markup.
    nasty = 'ls [a-z]* [x=y="list_dir", z]'
    for _done, _ok in ((False, False), (True, True), (True, False)):
        _Content.from_markup(head_markup("bash", nasty, _done, _ok))
    _Content.from_markup(head_markup(nasty, nasty, True, True))
    assert isinstance(body_text('[x=y="a", b]', "d"), Text)
    print("✅ tool_activity self-test OK (summarize + truncate + markup)")
