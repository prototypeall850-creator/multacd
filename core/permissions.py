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

# ── Search (baca internet, tanpa akses konten → selalu auto, tanpa override) ──
SEARCH_TOOLS = frozenset({"web_search"})

# ── Research (ASK: akses internet + bakar token LLM) ──
RESEARCH_TOOLS = frozenset({"quick_research", "deep_research", "export_research"})

# ── Personal (Telegram & scheduler — Phase 4) ──
# send_telegram default AUTO (teks); eskalasi ke ASK kalau content = file.
# get_jobs/daemon_status selalu AUTO; schedule/cancel selalu ASK
# (efek persist, tanpa override config).
PERSONAL_AUTO = frozenset({
    "send_telegram",
    "get_jobs",
    "daemon_status",
})
PERSONAL_ASK = frozenset({
    "schedule_job",
    "cancel_job",
    "user_manager",
    "generate_briefing",
})
PERSONAL_TOOLS = PERSONAL_AUTO | PERSONAL_ASK

# ── Code execution (jalankan kode → selalu konfirmasi, tanpa override config) ──
CODE_TOOLS = frozenset({
    "run_python",
    "run_tests",
})

# ── Tool berisiko tinggi: tanpa opsi [A] (session-approve terlalu berbahaya).
# Single source of truth — dipakai UI permission (popup) DAN guard session
# approval di bawah (dulu duplikat di tui/widgets/permission_popup.py).
RISKY_TOOLS = frozenset({"delete_file", "git_push"})

# Tool yang TIDAK BOLEH di-approve sekaligus untuk satu sesi via [A]:
# eksekusi kode & research kontraknya "selalu ask", tool risky terlalu
# merusak untuk di-auto-kan. UI tidak boleh bisa bypass kontrak ini.
NO_SESSION_APPROVAL = CODE_TOOLS | RESEARCH_TOOLS | RISKY_TOOLS

AUTO_APPROVED: frozenset[str] = READ_TOOLS | META_TOOLS | GIT_TOOLS | SEARCH_TOOLS | PERSONAL_AUTO
ASK_REQUIRED: frozenset[str] = WRITE_TOOLS | BASH_TOOLS | WEB_TOOLS | CODE_TOOLS | RESEARCH_TOOLS | PERSONAL_ASK
KNOWN_TOOLS: frozenset[str] = AUTO_APPROVED | ASK_REQUIRED

# ── Plugin tools (Phase 5 Step 2, mutable overlay) ──
# Plugin daftar di sini saat load (core/plugin_loader). Terpisah dari
# frozenset di atas supaya registry ↔ permissions check saat import
# (lihat tools/registry.py) tidak pecah sebelum plugin di-load.
# Default "ask" kalau plugin tidak deklarasikan permission (aman).
PLUGIN_PERMISSIONS: dict[str, Decision] = {}


def register_plugin_permission(tool_name: str, level: str = "ask") -> None:
    """Daftarkan permission tool plugin. Level selain auto/ask → ask."""
    PLUGIN_PERMISSIONS[tool_name] = "auto" if level == "auto" else "ask"


def unregister_plugin_permission(tool_name: str) -> None:
    """Cabut permission plugin (buat test / reload)."""
    PLUGIN_PERMISSIONS.pop(tool_name, None)


def check_permission(tool_name: str, config: Config | None = None) -> Decision:
    """Return `auto` (langsung jalan), `ask` (konfirmasi dulu), atau
    `deny` (tidak dikenal / tidak diizinkan).

    `config=None` → pakai default plan (read auto, write/bash/web ask).
    """
    if tool_name in META_TOOLS or tool_name in GIT_TOOLS:
        return "auto"
    if tool_name in SEARCH_TOOLS:
        return "auto"  # search saja: tanpa override config, selalu jalan
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
    if tool_name in RESEARCH_TOOLS:
        return "ask"  # research: internet + token, tanpa override config
    if tool_name in PERSONAL_ASK:
        return "ask"  # schedule/cancel: efek persist, tanpa override
    if tool_name in PERSONAL_TOOLS:
        return "auto"  # eskalasi file→ask ditangani PermissionChecker
    if tool_name in PLUGIN_PERMISSIONS:
        return PLUGIN_PERMISSIONS[tool_name]
    return "deny"


class PermissionChecker:
    """Resolver stateful per sesi — pegang override [A] Izinkan Semua Sesi Ini.

    Opsi [A] hanya berlaku untuk sesi ini; sesi baru = instance baru.
    TIDAK berlaku untuk NO_SESSION_APPROVAL (eksekusi kode, research,
    tool risky) — kontrak "selalu ask" tidak bisa dibypass UI.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config
        self._session_auto: set[str] = set()

    def approve_all_for_session(self, tool_name: str) -> None:
        """User tekan [A] — tool ini auto sampai sesi berakhir.

        Diabaikan untuk NO_SESSION_APPROVAL (Bug 2: dulu [A] di run_python
        membuat eksekusi kode auto sampai sesi berakhir).
        """
        if tool_name in NO_SESSION_APPROVAL:
            return
        self._session_auto.add(tool_name)

    def check(self, tool_name: str, params: dict[str, Any] | None = None) -> Decision:
        # Defense in depth: meski _session_auto tercemar (mutasi langsung),
        # tool selalu-ask/risky tetap tidak pernah auto via session.
        if tool_name in self._session_auto and tool_name not in NO_SESSION_APPROVAL:
            return "auto"
        # Eskalasi param-aware: lint + fix=true berarti tulis file.
        if tool_name == "lint_python" and (params or {}).get("fix") in (True, "true", "1"):
            return "ask"
        # Eskalasi param-aware: send_telegram dengan content file → ask.
        if tool_name == "send_telegram":
            from tools.personal.send_telegram import is_file_content
            if is_file_content((params or {}).get("content", "")):
                return "ask"
        # #4: git_commit selalu minta approve (dialog Pakai/Edit) — commit
        # tanpa terlihat itu cara tercepat kehilangan kepercayaan user.
        if tool_name == "git_commit":
            return "ask"
        # #4: git_push ke branch dilindungi → dialog (opsi buat branch baru).
        # allow_protected=true = LLM sudah opt-in eksplisit → auto normal.
        # Branch biasa → auto (tidak cerewet tiap push fitur).
        if tool_name == "git_push" and not (params or {}).get("allow_protected"):
            from tools.git.git_push import PROTECTED_BRANCHES, _current_branch
            target = (params or {}).get("branch", "") or ""
            target = target.strip() or (_current_branch(
                str((params or {}).get("workdir", "."))) or "")
            if not target or target in PROTECTED_BRANCHES:
                return "ask"  # tak ter-resolve = aman: tanya dulu
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
    # KECUALI eksekusi kode, research, dan schedule/cancel (efek persist) —
    # selalu ask, tanpa override.
    yolo = Config(model="m", api_key="k", auto_approve_reads=True,
                  ask_before_write=False, ask_before_bash=False, ask_before_web=False)
    for t in sorted(KNOWN_TOOLS - CODE_TOOLS - RESEARCH_TOOLS - PERSONAL_ASK):
        assert check_permission(t, yolo) == "auto", t
    for t in sorted(CODE_TOOLS | RESEARCH_TOOLS | PERSONAL_ASK):
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

    # [A] TIDAK berlaku untuk tool selalu-ask & risky (fix Bug 2):
    # eksekusi kode, research, delete_file tetap ask selamanya.
    checker2 = PermissionChecker()
    for t in sorted(NO_SESSION_APPROVAL - GIT_TOOLS):
        checker2.approve_all_for_session(t)
        assert checker2.check(t) == "ask", t
    # git_push auto by category HANYA buat branch biasa; di branch
    # dilindungi (atau tak ter-resolve) → ask (dialog + opsi buat branch).
    # [A] tidak berlaku (RISKY) — session-approve tak mengubahnya.
    checker2.approve_all_for_session("git_push")
    assert checker2.check("git_push", {"branch": "fitur-x"}) == "auto"
    assert checker2.check("git_push", {"branch": "main"}) == "ask"
    assert checker2.check("git_push", {"branch": "main",
                                       "allow_protected": True}) == "auto"
    # ...tapi tool biasa (bash, write_file) tetap bisa session-approved.
    checker2.approve_all_for_session("bash")
    assert checker2.check("bash") == "auto"

    # Eskalasi lint: fix=true (bool/string) → ask; default tetap auto.
    assert PermissionChecker().check("lint_python") == "auto"
    assert PermissionChecker().check("lint_python", {"fix": False}) == "auto"
    assert PermissionChecker().check("lint_python", {"fix": True}) == "ask"
    assert PermissionChecker().check("lint_python", {"fix": "true"}) == "ask"

    # Eskalasi send_telegram: teks auto, file ask.
    assert PermissionChecker().check("send_telegram") == "auto"
    assert PermissionChecker().check(
        "send_telegram", {"content": "halo"}) == "auto"
    assert PermissionChecker().check(
        "send_telegram", {"content": __file__}) == "ask"

    # #4: git_commit selalu ask (dialog Pakai/Edit) walau anggota GIT_TOOLS.
    assert check_permission("git_commit") == "auto"  # kategori tetap
    assert PermissionChecker().check("git_commit") == "ask"
    assert PermissionChecker().check(
        "git_commit", {"message": "x"}) == "ask"

    # Plugin overlay: default ask, auto eksplisit, unknown tetap deny.
    assert check_permission("plugin_xyz") == "deny"
    register_plugin_permission("plugin_xyz")
    assert check_permission("plugin_xyz") == "ask"
    register_plugin_permission("plugin_xyz", "auto")
    assert check_permission("plugin_xyz") == "auto"
    register_plugin_permission("plugin_xyz", "ngawur")
    assert check_permission("plugin_xyz") == "ask"
    unregister_plugin_permission("plugin_xyz")
    assert check_permission("plugin_xyz") == "deny"

    print(f"✅ permissions self-test OK ({len(KNOWN_TOOLS)} tools: "
          f"{len(AUTO_APPROVED)} auto, {len(ASK_REQUIRED)} ask)")
