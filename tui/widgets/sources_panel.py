"""Sources Panel — panel kanan mode /research (toggle Ctrl+R).

Isi: daftar sumber + ikon status, round counter, statistik, tombol export.
Digerakkan oleh event orchestrator (lihat core/research/orchestrator.py)
yang diteruskan MainScreen._apply_research_event.

Ikon status: . antri  > aktif  * full  ~ snippet  x gagal
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any
from urllib.parse import urlsplit

from textual import events
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Label, ListItem, ListView, Static

STATUS_ICONS = {
    "queued": ".",
    "searching": ">",
    "scraped": "*",
    "snippet": "~",
    "failed": "x",
}

PREVIEW_CHARS = 600


class SourcePreviewRequested(Message):
    """Klik/Enter sumber → MainScreen tampilkan preview di chat."""

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url


class ExportResearchRequested(Message):
    """Tombol Export → MainScreen minta agent simpan ke .md."""


def _domain(url: str) -> str:
    try:
        return urlsplit(url).netloc or url
    except ValueError:
        return url


class SourcesPanel(Vertical):
    """Panel kanan research. Hidden default, methods dipanggil sync."""

    def __init__(self) -> None:
        super().__init__(id="sources-panel")
        self._items: list[dict[str, Any]] = []  # {url,title,status,preview}
        self._round = (0, 0)
        self._queries = 0
        self._notice = ""

    def compose(self):
        yield Static("Sources (0)", id="sources-header")
        yield ListView(id="sources-list")
        yield Static("", id="sources-stats")
        yield Static("", id="sources-notice")
        yield Button("Export .md", id="sources-export")

    def on_mount(self) -> None:
        self.query_one("#sources-export", Button).display = False
        self._render_stats()

    # ── update dari orchestrator ──
    def update_sources(self, items: list[dict[str, Any]]) -> None:
        """Ganti daftar sumber (event 'sources')."""
        self._items = [{
            "url": it.get("url", ""),
            "title": it.get("title", "") or _domain(it.get("url", "")),
            "status": it.get("status", "searching"),
            "preview": (it.get("preview", "") or "")[:PREVIEW_CHARS],
        } for it in items]
        self._rebuild_list()
        self.query_one("#sources-header", Static).update(
            f"Sources ({len(self._items)})")
        self._render_stats()

    def update_source(self, url: str, status: str, preview: str = "") -> None:
        """Update status satu sumber (event 'source')."""
        for it in self._items:
            if it["url"] == url:
                it["status"] = status
                if preview:
                    it["preview"] = preview[:PREVIEW_CHARS]
                break
        else:
            self._items.append({"url": url, "title": _domain(url),
                                "status": status,
                                "preview": preview[:PREVIEW_CHARS]})
            self.query_one("#sources-header", Static).update(
                f"Sources ({len(self._items)})")
        self._rebuild_list()
        self._render_stats()

    def set_round(self, current: int, total: int) -> None:
        self._round = (current, total)
        self._render_stats()

    def add_queries(self, n: int) -> None:
        self._queries += n
        self._render_stats()

    def set_notice(self, text: str) -> None:
        self._notice = text
        with suppress(Exception):
            self.query_one("#sources-notice", Static).update(text)

    def set_export_visible(self, visible: bool) -> None:
        with suppress(Exception):
            self.query_one("#sources-export", Button).display = visible

    def reset(self) -> None:
        self._items = []
        self._round = (0, 0)
        self._queries = 0
        self._notice = ""
        try:
            self.query_one("#sources-header", Static).update("Sources (0)")
            self.query_one("#sources-list", ListView).clear()
            self.set_export_visible(False)
            self.set_notice("")
            self._render_stats()
        except Exception:
            pass

    def get_preview(self, url: str) -> str:
        for it in self._items:
            if it["url"] == url:
                body = it["preview"] or "(tidak ada preview konten)"
                cut = ""
                if len(it["preview"]) >= PREVIEW_CHARS:
                    cut = "\n…(dipotong — buka URL buat utuh)"
                return f"{it['title']}\n{url}\n\n{body}{cut}"
        return f"(sumber tidak dikenal: {url})"

    # ── interaksi ──
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self._index_of(event.item)
        if idx is not None:
            self.post_message(
                SourcePreviewRequested(self._items[idx]["url"]))

    async def on_key(self, event: events.Key) -> None:
        # Permission menunggu → Y/N/A/Esc jawab dulu (Enter tetap preview).
        if event.key.lower() in ("y", "n", "a", "e", "b", "escape"):
            try:
                from tui.widgets.permission_popup import PermissionPopup
                perm = self.screen.query_one(PermissionPopup)
            except Exception:
                return
            if perm.is_waiting and perm.answer_key(event.key):
                event.prevent_default()
                event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sources-export":
            self.post_message(ExportResearchRequested())

    # ── internal ──
    def _index_of(self, item: ListItem) -> int | None:
        try:
            lst = self.query_one("#sources-list", ListView)
            return list(lst.children).index(item)
        except ValueError:
            return None

    def _label(self, it: dict[str, Any]) -> str:
        icon = STATUS_ICONS.get(it["status"], "?")
        return f"{icon} {it['title']} ({_domain(it['url'])})"

    def _rebuild_list(self) -> None:
        try:
            lst = self.query_one("#sources-list", ListView)
        except Exception:
            return
        lst.clear()
        for it in self._items:
            lst.append(ListItem(Label(self._label(it))))

    def _render_stats(self) -> None:
        read = sum(1 for it in self._items
                   if it["status"] in ("scraped", "snippet"))
        cur, tot = self._round
        with suppress(Exception):
            self.query_one("#sources-stats", Static).update(
                f"Round: {cur}/{tot} · Read: {read}/{len(self._items)} "
                f"· Queries: {self._queries}")


if __name__ == "__main__":
    # Pure logic tanpa app (mount butuh Textual pilot — diuji via pilot).
    assert _domain("https://arxiv.org/abs/2501.x?q=1") == "arxiv.org"
    for st, icon in [("searching", ">"), ("scraped", "*"),
                     ("snippet", "~"), ("failed", "x"), ("queued", ".")]:
        assert STATUS_ICONS[st] == icon
    print("✅ sources_panel self-test OK (domain + ikon)")
