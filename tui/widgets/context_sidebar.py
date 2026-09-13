"""Right context sidebar TUI-R1 — bungkus InfoPanel + seksi MCP.

Manfaatkan widget existing: InfoPanel (project/git/token/cost/model)
tetap yang render + update path-nya (`MainScreen._refresh_info` tak
berubah target). Tambah Static MCP read-only di bawahnya.

MCP: belum ada service registry di codebase → tampil "—" (jujur,
TUI_REDESIGN.md §20: jangan fake angka). `get_mcp_servers()` adalah
adapter read-only — TUI-R5 tinggal isi tanpa ubah widget.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Static

from tui.widgets.info_panel import InfoPanel


def render_mcp(servers: list[dict[str, Any]]) -> str:
    """Blok MCP compact. Pure function. Kosong = '—', bukan fake list."""
    if not servers:
        return "MCP\n—"
    lines = ["MCP"]
    for srv in servers:
        name = str(srv.get("name", "?"))
        status = str(srv.get("status", "?"))
        mark = "●" if status.lower() == "connected" else "○"
        lines.append(f"{mark} {name}  {status}")
    return "\n".join(lines)


def get_mcp_servers() -> list[dict[str, Any]]:
    """Adapter read-only status MCP. Belum ada registry → []."""
    return []


class ContextSidebar(Vertical):
    """Sidebar kanan: InfoPanel existing + blok MCP. Permanen saat lega."""

    def __init__(self) -> None:
        super().__init__(id="context-sidebar")

    def compose(self):
        yield InfoPanel()
        yield Static("", id="mcp-body")

    def set_mcp(self, servers: list[dict[str, Any]] | None = None) -> None:
        """Refresh blok MCP (dipanggil screen; default baca adapter)."""
        text = render_mcp(get_mcp_servers() if servers is None else servers)
        with suppress(Exception):  # belum mount saat dipanggil dari test
            self.query_one("#mcp-body", Static).update(Text(text))


if __name__ == "__main__":
    assert render_mcp([]) == "MCP\n—"
    s = render_mcp([{"name": "figma", "status": "Connected"},
                    {"name": "github", "status": "Disabled"}])
    assert "● figma  Connected" in s and "○ github  Disabled" in s
    assert get_mcp_servers() == []
    side = ContextSidebar.__new__(ContextSidebar)
    side.set_mcp([])  # tanpa mount: no-crash (suppress)
    print("✅ context_sidebar self-test OK")
