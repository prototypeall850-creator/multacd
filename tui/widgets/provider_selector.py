"""Provider selector popup TUI-R4 — pilih LLM/search provider (§14).

Data id/label dari setup_wizard (single source); status connected/aktif
di-supply screen dari cfg — widget tak baca config global, tak simpan apa
pun. Pilih → screen jalankan alur key/base existing (`/connect <id>`).

Baris: ("head", label) header disabled | ("llm"/"search", id, label, flag).
"""

from __future__ import annotations

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Label, ListItem, ListView, Static

Row = tuple  # ("head", label) | (kind, id, label, flag)


def build_rows(llm: list[tuple[str, str, bool]],
               search: list[tuple[str, str, bool]]) -> list[Row]:
    """Susun baris grouped. Pure function. Grup kosong disembunyikan."""
    rows: list[Row] = []
    if llm:
        rows.append(("head", "Provider LLM"))
        rows += [("llm", i, label, conn) for i, label, conn in llm]
    if search:
        rows.append(("head", "Provider search"))
        rows += [("search", i, label, active) for i, label, active in search]
    return rows


def render_row(row: Row) -> Text:
    """'● Groq  connected' / '○ Custom  belum'. Pure function."""
    t = Text()
    if row[0] == "head":
        t.append(str(row[1]), style="bold dim")
        return t
    _, _pid, label, flag = row
    if row[0] == "llm":
        mark, st = ("●", "connected") if flag else ("○", "belum")
        color = "green" if flag else "dim"
    else:
        mark, st = ("●", "aktif") if flag else ("○", "—")
        color = "green" if flag else "dim"
    t.append(f"{mark} ", style=color)
    t.append(label)
    t.append(f"  {st}", style="dim")
    return t


class ProviderSelector(Vertical):
    """Popup pilih provider. State di sini, aksi via screen."""

    def __init__(self) -> None:
        super().__init__(id="provider-selector")
        self._rows: list[Row] = []
        self._index = 0

    def compose(self):
        yield Static("Connect provider   esc", id="provider-title")
        yield ListView(id="provider-list")

    @property
    def is_open(self) -> bool:
        return self.display

    @property
    def selected(self) -> tuple[str, str] | None:
        """(kind, id) terpilih. None = header/kosong."""
        if not self._rows or self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        if row[0] == "head":
            return None
        return (row[0], row[1])

    def open(self, llm: list[tuple[str, str, bool]],
             search: list[tuple[str, str, bool]]) -> None:
        self._rows = build_rows(llm, search)
        self._index = next((i for i, r in enumerate(self._rows)
                            if r[0] != "head"), 0)
        self._rebuild()
        self.display = True

    def close(self) -> None:
        self.display = False
        self._rows = []
        self._index = 0

    def move(self, delta: int) -> None:
        if not self._rows:
            return
        n = len(self._rows)
        for _ in range(n):  # lompat header, tak pernah infinite
            self._index = (self._index + delta) % n
            if self._rows[self._index][0] != "head":
                break
        self._highlight()

    def _rebuild(self) -> None:
        try:
            lst = self.query_one("#provider-list", ListView)
        except Exception:
            return
        lst.clear()
        for row in self._rows:
            if row[0] == "head":
                item = ListItem(Label(render_row(row)), disabled=True)
            else:
                item = ListItem(Label(render_row(row)))
            lst.append(item)
        self._highlight()

    def _highlight(self) -> None:
        try:
            lst = self.query_one("#provider-list", ListView)
            if self._rows:
                lst.index = self._index
        except Exception:
            pass

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Klik item → pilih (kayak palette/selector lain)."""
        try:
            idx = list(self.query_one("#provider-list", ListView).children).index(
                event.item)
        except ValueError:
            return
        if 0 <= idx < len(self._rows) and self._rows[idx][0] != "head":
            self._index = idx
            screen = self.screen
            if hasattr(screen, "provider_select"):
                screen.provider_select()


if __name__ == "__main__":
    rows = build_rows([("groq", "Groq", True), ("custom", "Custom", False)],
                      [("tavily", "Tavily", True)])
    assert [r[0] for r in rows] == ["head", "llm", "llm", "head", "search"]
    assert "connected" in str(render_row(rows[1]))
    assert "belum" in str(render_row(rows[2]))
    assert "aktif" in str(render_row(rows[4]))
    assert build_rows([], []) == []
    sel = ProviderSelector()
    sel.open([("groq", "Groq", True)], [])
    assert sel.is_open and sel.selected == ("llm", "groq")
    sel.move(1)
    assert sel.selected == ("llm", "groq")  # 1 item: wrap tetap
    sel.close()
    assert not sel.is_open and sel.selected is None
    print("✅ provider_selector self-test OK (rows + nav)")
