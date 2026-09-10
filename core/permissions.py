"""Permission system — tool mana yang langsung jalan vs minta konfirmasi.

Kategori persis seperti PLAN Section 6:
  AUTO-APPROVED : filesystem READ + meta-agent + SEMUA git ops
  ASK           : filesystem WRITE + bash + web_fetch
  DENY          : nama tool yang tidak dikenal (halusinasi LLM) → tolak

Test cepat:
    python -m core.permissions
"""

from __future__ import annotations

from typing import Any, Literal

from core.config import Config

Decision = Literal["auto", "ask", "deny"]

# ── Filesystem READ (tidak mengubah apapun) ──
# NOTE: lint_python di sini (default fix=False = baca saja). Kalau dipanggil
# dengan fix=true, PermissionChecker.check() eskalasi ke "ask" via params
# (satu-satunya tool yang param-aware — lihat check() di bawah).
READ_TOOLS = frozenset({
    "read_file",
    "read_many_files",
    "glob",
    "grep",
    "list_dir",
    "scan_codebase",
    "lint_python",
})

# ── Meta-agent (tidak menyentuh filesystem) ──
META_TOOLS = frozenset({
    "task",
    "ask",
    "skill",
    "todo_write",
    "remember",
    "recall",
    "forget",
})

# ── Git (semua operasi — sesuai PLAN Section 6) ──
GIT_TOOLS = frozenset({
    "git_status",
    "git_diff",
    "git_log",
    "git_branch",
    "git_add",
    "git_commit",
    "git_push",
    "git_pull",
    "git_checkout",
    "git_merge",
})

# ── Filesystem WRITE (bisa merusak/mengubah file) ──
WRITE_TOOLS = frozenset({
    "write_file",
    "edit_file",
    "multi_edit",
    "apply_patch",
    "move_file",
    "delete_file",  # ⚠️ tidak bisa di-undo
})

# ── Shell & Web ──
BASH_TOOLS = frozenset({"bash"})  # ⚠️ bisa apa saja
WEB_TOOLS = frozenset({"web_fetch", "web_scrape"})

# ── Code execution (jalankan kode → selalu konfirmasi, tanpa override config) ──
CODE_TOOLS = frozenset({
    "run_python",
    "run_tests",
})

AUTO_APPROVED: frozenset[str] = READ_TOOLS | META_TOOLS | GIT_TOOLS
ASK_REQUIRED: frozenset[str] = WRITE_TOOLS | BASH_TOOLS | WEB_TOOLS | CODE_TOOLS
KNOWN_TOOLS: frozenset[str] = AUTO_APPROVED | ASK_REQUIRED


def check_permission(tool_name: str, config: Config | None = None) -> Decision:
    """Return `auto` (langsung jalan), `ask` (konfirmasi dulu), atau
    `deny` (tidak dikenal / tidak diizinkan).

    `config=None` → pakai default plan (read auto, write/bash/web ask).
    """
    if tool_name in META_TOOLS or tool_name in GIT_TOOLS:
        return "auto"
    if tool_name in READ_TOOLS:
        if config is not None and not config.auto_approve_reads:
            return "ask"
        return "auto"
    if tool_name in WRITE_TOOLS:
        if config is not None and not config.ask_before_write:
            return "auto"
        return "ask"
    if tool_name in BASH_TOOLS:
        if config is not None and not config.ask_before_bash:
            return "auto"
        return "ask"
    if tool_name in WEB_TOOLS:
        if config is not None and not config.ask_before_web:
            return "auto"
        return "ask"
    if tool_name in CODE_TOOLS:
        return "ask"  # eksekusi kode: tanpa override config, selalu tanya
    return "deny"


class PermissionChecker:
    """Resolver stateful per sesi — pegang override [A] Izinkan Semua Sesi Ini.

    Opsi [A] hanya berlaku untuk sesi ini; sesi baru = instance baru.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config
        self._session_auto: set[str] = set()

    def approve_all_for_session(self, tool_name: str) -> None:
        """User tekan [A] — tool ini auto sampai sesi berakhir."""
        self._session_auto.add(tool_name)

    def check(self, tool_name: str, params: dict[str, Any] | None = None) -> Decision:
        if tool_name in self._session_auto:
            return "auto"
        # Eskalasi param-aware: lint + fix=true berarti tulis file.
        if tool_name == "lint_python" and (params or {}).get("fix") in (True, "true", "1"):
            return "ask"
        return check_permission(tool_name, self.config)


if __name__ == "__main__":
    # Default plan: read/meta/git auto, write/bash/web ask, unknown deny.
    for t in sorted(AUTO_APPROVED):
        assert check_permission(t) == "auto", t
    for t in sorted(ASK_REQUIRED):
        assert check_permission(t) == "ask", t
    assert check_permission("rm_rf_semua") == "deny"
    assert check_permission("") == "deny"

    # Override config: user matikan semua ask → semua known jadi auto,
    # KECUALI eksekusi kode (CODE_TOOLS selalu ask, tanpa override).
    yolo = Config(model="m", api_key="k", auto_approve_reads=True,
                  ask_before_write=False, ask_before_bash=False, ask_before_web=False)
    for t in sorted(KNOWN_TOOLS - CODE_TOOLS):
        assert check_permission(t, yolo) == "auto", t
    for t in sorted(CODE_TOOLS):
        assert check_permission(t, yolo) == "ask", t

    # Override config: paranoid → read pun ikut ask.
    paranoid = Config(model="m", api_key="k", auto_approve_reads=False)
    for t in sorted(READ_TOOLS):
        assert check_permission(t, paranoid) == "ask", t
    # ...tapi meta & git tetap auto (tidak terpengaruh override read).
    for t in sorted(META_TOOLS | GIT_TOOLS):
        assert check_permission(t, paranoid) == "auto", t

    # Session override [A]: ask → auto hanya di sesi itu.
    checker = PermissionChecker()
    assert checker.check("write_file") == "ask"
    checker.approve_all_for_session("write_file")
    assert checker.check("write_file") == "auto"
    assert PermissionChecker().check("write_file") == "ask"  # sesi baru = reset

    # Eskalasi lint: fix=true (bool/string) → ask; default tetap auto.
    assert PermissionChecker().check("lint_python") == "auto"
    assert PermissionChecker().check("lint_python", {"fix": False}) == "auto"
    assert PermissionChecker().check("lint_python", {"fix": True}) == "ask"
    assert PermissionChecker().check("lint_python", {"fix": "true"}) == "ask"

    print(f"✅ permissions self-test OK ({len(KNOWN_TOOLS)} tools: "
          f"{len(AUTO_APPROVED)} auto, {len(ASK_REQUIRED)} ask)")
