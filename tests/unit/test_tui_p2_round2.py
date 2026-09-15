"""QA ronde-2 (issue #56): edge case fix audit M4/M3/M7/M1 + C1 dialog.

Fokus verifikasi perilaku (bukan implementasi):
  a. /clear TUI-local: context beneran kosong; "/clear <pesan>" tetap
     clear (paritas dgn intercept lama di agent_loop/mode_manager).
  b. /clear saat idle vs bg vs jendela cleanup M3 — guard worker tak
     boleh menolak /clear selamanya.
  c. Esc saat ContinueDialog terbuka (screen terpisah): TIDAK membatalkan
     turn; Enter "lanjut" tetap jalan; binding dialog tak berubah.
  d. M7: Esc dari InputBar fokus + permission waiting → jawab "no"
     MASIH berfungsi (rantai baru tak bolong dua arah).
"""

from __future__ import annotations

import asyncio
import os

import pytest
from textual.widgets import Button

os.environ.setdefault("MULTACD_HOME", "/tmp/opencode/test-p2r2")

from core.agent_events import AgentContinue, AgentText, AgentToolDone, AgentToolStart
from core.config import Config
from core.mode_manager import ModeManager
from core.session_state import SessionState
from tui.app import MultacdApp
from tui.widgets.chat_panel import ChatPanel
from tui.widgets.confirm_dialog import ContinueDialog
from tui.widgets.file_tree import ProjectTree
from tui.widgets.footer_bar import FooterBar
from tui.widgets.input_bar import InputBar
from tui.widgets.permission_popup import PermissionPopup
from tui.widgets.slash_palette import SlashPalette
from tui.widgets.thinking_bar import ThinkingBar


def _plain(widget) -> str:
    try:
        r = widget.render()
        return str(getattr(r, "plain", r))
    except Exception:
        return ""


def _cancel_msgs(chat: ChatPanel) -> int:
    return sum("Turn dibatalkan" in _plain(w) for w in chat.children)


class StubController:
    """Tool start lalu ngambang — jendela cancel/bg (sama dgn ronde-1)."""

    def __init__(self, session: SessionState) -> None:
        self.session = session

    async def run_turn(self, text, hooks, active_tools=None):
        self.session.begin_turn()
        try:
            await hooks.emit(AgentToolStart("c1", "bash",
                                            {"command": "sleep 5"}))
            await asyncio.sleep(5)
        finally:
            self.session.end_turn()


class StubControllerPerm:
    """confirm() → popup waiting; jawab lanjut turn (dipakai butir d)."""

    def __init__(self, session: SessionState) -> None:
        self.session = session
        self.answer: str | None = None

    async def run_turn(self, text, hooks, active_tools=None):
        self.session.begin_turn()
        try:
            self.answer = await hooks.confirm("write_file", {"path": "a.py"})
            await hooks.emit(AgentText(f"answered:{self.answer}"))
            await asyncio.sleep(0.5)
        finally:
            self.session.end_turn()


class StubControllerContinue:
    """Emit AgentContinue via hooks → ContinueDialog ter-push (butir c)."""

    def __init__(self, session: SessionState) -> None:
        self.session = session
        self.choice: bool | None = None

    async def run_turn(self, text, hooks, active_tools=None):
        self.session.begin_turn()
        try:
            self.choice = await hooks.continue_prompt(
                AgentContinue(tool_count=3, limit=5, summary="bash x3"))
            await hooks.emit(AgentText(f"setelah:{self.choice}"))
            await asyncio.sleep(1)  # jendela observasi (dialog tutup,
            # worker HARUS masih hidup — Esc dialog ≠ cancel turn)
        finally:
            self.session.end_turn()


@pytest.fixture()
def app():
    return MultacdApp(Config(model="groq/llama-3.3-70b", api_key="k"))


async def _open_main(app, pilot):
    await app.pop_screen()
    for _ in range(3):
        await pilot.pause()
    return app.main_screen


async def _submit(screen, pilot, text: str) -> None:
    inp = screen.query_one("#input-bar", InputBar)
    inp.focus()
    inp.text = text
    for _ in range(2):
        await pilot.pause()
    await pilot.press("enter")


async def _wait_busy(screen, pilot, want: bool, tries: int = 100) -> None:
    for _ in range(tries):
        await pilot.pause()
        if screen.session.busy == want:
            return
    raise AssertionError(f"busy tak jadi {want}")


async def _settle_idle(s, pilot, tries: int = 100) -> None:
    foot = s.query_one(FooterBar)
    for _ in range(tries):
        await pilot.pause()
        if (not s.session.busy and s._turn_worker is None
                and foot._busy is False):
            return
    raise AssertionError("UI tak settle ke idle")


async def _seed_history(app, n: int = 2) -> int:
    """Tambah n pesan user/assistant → return jumlah pesan akhir."""
    app.context.add_message("user", "pesan lama")
    app.context.add_message("assistant", "jawab lama")
    return len(app.context.get_messages())


async def _wait_clear(s, pilot) -> None:
    """Tunggu worker ringan _clear_ui selesai (bukan turn worker)."""
    for _ in range(50):
        await pilot.pause()
        texts = " ".join(_plain(w) for w in
                         s.query_one(ChatPanel).children)
        if "History dibersihkan" in texts:
            return
    raise AssertionError("/clear UI tak selesai")


# ---------------------------------------------------------------- butir a


def test_r2_mode_manager_old_path_clears_with_arg():
    """Paritas lama: agent_loop intercept "/clear halo" JUGA = clear
    (cmd = parts[0]; arg dibuang, pesan tak pernah sampai LLM)."""
    mm = ModeManager()
    assert mm.handle_command("/clear halo").action == "clear"
    assert mm.handle_command("/clear").action == "clear"
    assert mm.handle_command("/clearall").action is None  # bukan prefiks


@pytest.mark.asyncio
async def test_r2_clear_with_trailing_message_clears_context(app):
    """a: "/clear halo" → context 1 system-only, TIDAK lewat turn/LLM
    (paritas penuh dgn intercept mode_manager lama)."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        calls: list[str] = []

        class Spy(StubController):
            async def run_turn(self, text, hooks, active_tools=None):
                calls.append(text)
                await super().run_turn(text, hooks, active_tools)

        s._agent_ctl = Spy(s.session)
        seeded = await _seed_history(app)
        assert seeded == 2  # context awal kosong + 2 seed (1 system pun belum ada)
        await _submit(s, pilot, "/clear halo")
        await _wait_clear(s, pilot)
        msgs = app.context.get_messages()
        assert [m["role"] for m in msgs] == ["system"]  # beneran kosong
        assert msgs[0]["content"] == app.composer.compose()
        assert s._turn_worker is None and not s.session.busy
        assert calls == []  # "halo" TIDAK dikirim ke agent/LLM
        chat = s.query_one(ChatPanel)
        texts = " ".join(_plain(w) for w in chat.children)
        assert "History dibersihkan" in texts
        assert "halo" not in texts  # arg ikut dibuang (sama kayak dulu)


@pytest.mark.asyncio
async def test_r2_clear_prefix_word_is_not_a_clear(app):
    """a (sisi lain): "/clearall" bukan command → lolos ke turn, context
    utuh (guard parts[0] == "/clear", bukan startswith)."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        calls: list[str] = []

        class Spy(StubController):
            async def run_turn(self, text, hooks, active_tools=None):
                calls.append(text)
                await super().run_turn(text, hooks, active_tools)

        s._agent_ctl = Spy(s.session)
        seeded = await _seed_history(app)
        # jalur programatik (klik tree/export): helper input tak dipakai
        # karena Enter untuk slash tak dikenal ditelan palette inline (R3,
        # pra-P2) — di luar cakupan M4.
        s._submit("/clearall")
        for _ in range(50):
            await pilot.pause()
            if calls:
                break
        assert calls == ["/clearall"]
        assert len(app.context.get_messages()) == seeded  # tak ke-clear
        await pilot.press("escape")
        await _settle_idle(s, pilot)


# ---------------------------------------------------------------- butir b


@pytest.mark.asyncio
async def test_r2_clear_while_bg_active_blocked_context_intact(app):
    """b: /clear saat task di-background → diblok jujur (perilaku lama),
    context utuh, worker tak ditimpa; setelah turn selesai /clear jalan."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s._agent_ctl = StubController(s.session)
        seeded = await _seed_history(app)
        await _submit(s, pilot, "cari sesuatu")
        await _wait_busy(s, pilot, want=True)
        s.action_background_task()  # Ctrl+B
        for _ in range(3):
            await pilot.pause()
        assert s._bg_active and s.session.busy
        ref = s._turn_worker
        s._submit("/clear")  # jalur non-input saat bg
        for _ in range(5):
            await pilot.pause()
        assert s._turn_worker is ref  # worker lama utuh
        assert len(app.context.get_messages()) == seeded  # TIDAK ke-clear
        texts = " ".join(_plain(w) for w in s.query_one(ChatPanel).children)
        assert "Agent jalan di background" in texts
        assert "History dibersihkan" not in texts

        await pilot.press("escape")  # bersihkan turn bg
        await _settle_idle(s, pilot)
        s._submit("/clear")  # setelah idle → harus lolos
        await _wait_clear(s, pilot)
        assert [m["role"] for m in app.context.get_messages()] == ["system"]


@pytest.mark.asyncio
async def test_r2_clear_during_cleanup_window_deferred_then_works(app):
    """b+M3: jendela busy=False/_turn_worker≠None → /clear DITOLAK
    (by design, jangan timpa cleanup); SETELAH settle /clear wajib jalan
    — guard tak boleh nyangkut nolak selamanya."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s._agent_ctl = StubController(s.session)
        seeded = await _seed_history(app)
        await _submit(s, pilot, "cari sesuatu")
        chat = s.query_one(ChatPanel)
        for _ in range(100):
            await pilot.pause()
            if "c1" in chat._tool_rows and s.session.busy:
                break
        # perlambat kosmetik except → jendela M3 pasti kebuka
        orig_info = chat.add_info

        async def slow_info(text: str) -> None:
            await asyncio.sleep(0.5)
            await orig_info(text)

        chat.add_info = slow_info
        await pilot.press("escape")
        for _ in range(100):
            await pilot.pause()
            if not s.session.busy and s._turn_worker is not None:
                break
        assert not s.session.busy and s._turn_worker is not None
        s._submit("/clear")  # dalam jendela → harus DITOLAK dulu
        await pilot.pause()
        assert len(app.context.get_messages()) == seeded

        await _settle_idle(s, pilot)
        assert s._turn_worker is None
        assert _cancel_msgs(chat) == 1  # M1: pesan cancel ada SEBELUM clear
        s._submit("/clear")  # setelah settle → lolos, guard lepas
        await _wait_clear(s, pilot)
        assert [m["role"] for m in app.context.get_messages()] == ["system"]


# ---------------------------------------------------------------- butir c


async def _open_continue_dialog(app, pilot, s) -> None:
    s._agent_ctl = StubControllerContinue(s.session)
    await _submit(s, pilot, "kerjakan")
    for _ in range(100):
        await pilot.pause()
        if isinstance(app.screen, ContinueDialog):
            return
    raise AssertionError("ContinueDialog tak ter-push")


@pytest.mark.asyncio
async def test_r2_esc_in_continue_dialog_not_cancel_turn(app):
    """c: Esc DI dialog = dismiss "berhenti" (binding lama), BUKAN cancel
    worker — turn lanjut normal sampai selesai, tanpa pesan 'dibatalkan'."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        await _open_continue_dialog(app, pilot, s)
        ctl = s._agent_ctl
        worker = s._turn_worker
        assert worker is not None and s.session.busy
        assert not worker.is_cancelled  # Esc widget bawah tak bocor ke sini
        assert _cancel_msgs(s.query_one(ChatPanel)) == 0

        await pilot.press("escape")  # Esc di screen dialog
        for _ in range(5):
            await pilot.pause()
        assert app.screen is s  # dialog tutup
        assert not worker.is_cancelled  # turn TIDAK dibatalkan
        assert s._turn_worker is worker  # ref utuh (jendela stub 2 dtk)
        assert s.session.busy  # masih jalan normal pasca-dialog
        await _settle_idle(s, pilot)
        assert ctl.choice is False  # dismiss = berhenti
        chat = s.query_one(ChatPanel)
        assert _cancel_msgs(chat) == 0  # bukan jalur Esc-cancel
        assert "Berhenti di batas iterasi" in " ".join(
            _plain(w) for w in chat.children)
        # stream SETELAH dialog tetap masuk → worker hidup terus:
        assert "setelah:False" in " ".join(chat._assistant_history)


@pytest.mark.asyncio
async def test_r2_continue_dialog_enter_lanjut_binding_intact(app):
    """c: Enter di dialog → "lanjut" (binding tak berubah), flow lanjut."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        await _open_continue_dialog(app, pilot, s)
        dlg = app.screen
        labels = [str(b.label) for b in dlg.query(Button)]
        assert any("Lanjut" in x for x in labels)
        assert any("Berhenti (Esc)" in x for x in labels)

        await pilot.press("enter")
        for _ in range(5):
            await pilot.pause()
        assert app.screen is s
        assert s._agent_ctl.choice is True
        await _settle_idle(s, pilot)
        chat = s.query_one(ChatPanel)
        assert _cancel_msgs(chat) == 0
        texts = " ".join(_plain(w) for w in chat.children)
        assert "Lanjut setelah 3 tool call" in texts
        assert "setelah:True" in " ".join(chat._assistant_history)


# ---------------------------------------------------------------- butir d


@pytest.mark.asyncio
async def test_r2_esc_from_focused_input_answers_permission_no(app):
    """d (M7): popup waiting + InputBar FOKUS → Esc lewat rantai baru
    screen._on_escape → jawab "no" (bukan no-op, bukan cancel turn)."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        ctl = StubControllerPerm(s.session)
        s._agent_ctl = ctl
        await _submit(s, pilot, "tulis file")
        perm = s.query_one(PermissionPopup)
        for _ in range(100):
            await pilot.pause()
            if perm.is_waiting and s.session.busy:
                break
        assert perm.is_waiting
        s.action_background_task()  # bg: input aktif lagi → bisa fokus
        for _ in range(3):
            await pilot.pause()
        inp = s.query_one(InputBar)
        assert inp.disabled is False
        inp.focus()
        for _ in range(2):
            await pilot.pause()
        assert inp.has_focus

        await pilot.press("escape")
        for _ in range(3):
            await pilot.pause()
        assert not perm.is_waiting  # BUKAN no-op: popup terjawab
        assert perm.display is False
        assert s.session.busy and s._turn_worker is not None  # turn utuh
        assert _cancel_msgs(s.query_one(ChatPanel)) == 0
        await _settle_idle(s, pilot)
        assert ctl.answer == "no"  # semantics lama Esc = no tetap
        chat = s.query_one(ChatPanel)
        assert "answered:no" in " ".join(chat._assistant_history)


# ------------------------------------- ronde-2 delta (MAJOR + MINOR m-A..m-F)


@pytest.mark.asyncio
async def test_r2_clear_refreshes_shell_usage(app):
    """m-A: /clear → shell (footer) di-refresh — token usage tidak basi
    permanen setelah context dibersihkan (estimasi turun ke ~system)."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        foot = s.query_one(FooterBar)
        app.context.add_message("user", "x" * 4000)
        s._refresh_shell()  # sinkron dengan state berbibit
        before = foot._usage
        s._submit("/clear")
        await _wait_clear(s, pilot)
        assert foot._usage != before, (before, foot._usage)


@pytest.mark.asyncio
async def test_r2_clear_resets_live_dict(app):
    """m-B: ChatPanel.clear() reset _live — widget live sudah kebuang
    bareng children; dict yatim bikin add_live_output berikutnya update
    widget yang sudah lepas dari DOM."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        chat = s.query_one(ChatPanel)
        await chat.add_tool_row("zz", "bash", {})
        await chat.add_live_output("zz", "out")
        assert "zz" in chat._live
        s._submit("/clear")
        await _wait_clear(s, pilot)
        assert chat._live == {}, chat._live
        assert "zz" not in chat._tool_rows


@pytest.mark.asyncio
async def test_r2_live_output_unknown_call_dropped_silently(app):
    """m-D: add_live_output cek ulang — call tanpa row tool = baris telat
   /artefak → dibuang senyap, bukan blok live yatim. Call ber-row → jalur
    normal tetap jalan."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        chat = s.query_one(ChatPanel)
        n = len(chat.children)
        await chat.add_live_output("hantu", "telat dari thread")
        assert chat._live == {}
        assert len(chat.children) == n  # tidak ada widget baru
        await chat.add_tool_row("c9", "bash", {})
        await chat.add_live_output("c9", "ok")
        assert "c9" in chat._live


@pytest.mark.asyncio
async def test_r2_esc_from_tree_focus_follows_screen_chain(app):
    """m-E: Esc saat tree fokus → satu pintu screen _on_escape — palette
    ditutup DULU sebelum permission dijawab (prioritas M7, dulu tree
    menjawab permission langsung dan mendahului rantai)."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        ctl = StubControllerPerm(s.session)
        s._agent_ctl = ctl
        await _submit(s, pilot, "tulis file")
        perm = s.query_one(PermissionPopup)
        for _ in range(100):
            await pilot.pause()
            if perm.is_waiting and s.session.busy:
                break
        s.action_background_task()  # input usable → hooks turn tetap jalan
        for _ in range(3):
            await pilot.pause()
        s.action_open_palette()
        s.action_toggle_tree()  # tampilkan + fokus tree
        tree = s.query_one(ProjectTree)
        tree.focus()
        for _ in range(2):
            await pilot.pause()
        assert tree.has_focus
        pal = s.query_one(SlashPalette)
        assert pal.overlay_open and perm.is_waiting

        await pilot.press("escape")  # dari fokus TREE
        for _ in range(3):
            await pilot.pause()
        assert not pal.display  # rantai: palette dulu
        assert perm.is_waiting  # permission BELUM dijawab
        assert ctl.answer is None

        await pilot.press("escape")  # Esc #2: sekarang jawab izin
        for _ in range(3):
            await pilot.pause()
        assert not perm.is_waiting
        await _settle_idle(s, pilot)
        assert ctl.answer == "no"  # semantics Esc = no tetap utuh


@pytest.mark.asyncio
async def test_r2_y_from_tree_still_answers_permission(app):
    """m-E sisi lain: y/n/a/e/b dari tree MASIH dijawab permission —
    hanya escape yang dikeluarkan dari daftar."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        ctl = StubControllerPerm(s.session)
        s._agent_ctl = ctl
        await _submit(s, pilot, "tulis file")
        perm = s.query_one(PermissionPopup)
        for _ in range(100):
            await pilot.pause()
            if perm.is_waiting and s.session.busy:
                break
        s.action_toggle_tree()
        tree = s.query_one(ProjectTree)
        tree.focus()
        for _ in range(2):
            await pilot.pause()
        assert tree.has_focus
        await pilot.press("y")
        for _ in range(3):
            await pilot.pause()
        assert not perm.is_waiting  # dijawab tree (jalur lama utuh)
        assert s.session.busy  # turn lanjut
        await _settle_idle(s, pilot)
        assert ctl.answer == "yes"


@pytest.mark.asyncio
async def test_r2_widget_query_failure_does_not_stick_worker(app):
    """m-F: query widget di luar try (lama) → raise = finally tak jalan =
    _turn_worker nyangkut non-None selamanya (submit/Esc mati). Sekarang
    query di dalam try → finally reset state, submit berikutnya jalan."""
    from textual.css.query import NoMatches

    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        orig_qo = type(s).query_one
        orig_rw = type(s).run_worker

        def flaky_qo(self, selector, *args, **kwargs):
            if selector is ThinkingBar:
                raise NoMatches("m-F probe")
            return orig_qo(self, selector, *args, **kwargs)

        def safe_worker(self, coro, **kwargs):
            # worker error tak boleh bunuh app di test — fokus ke state
            return orig_rw(self, coro, exit_on_error=False, **kwargs)

        s.query_one = flaky_qo.__get__(s)
        s.run_worker = safe_worker.__get__(s)
        s._agent_ctl = StubController(s.session)
        s._submit("pertama")  # _run_turn raise NoMatches di query ThinkingBar
        for _ in range(50):
            await pilot.pause()
            if s._turn_worker is None and not s.session.busy:
                break
        # m-F kunci: state ter-reset walau query gagal (dulu stuck selamanya)
        assert s._turn_worker is None and not s.session.busy

        # submit berikutnya harus jalan normal lagi:
        s.query_one = orig_qo.__get__(s)
        s.run_worker = orig_rw.__get__(s)
        s._agent_ctl = StubController(s.session)
        s._submit("kedua")
        await _wait_busy(s, pilot, want=True)
        await pilot.press("escape")
        await _settle_idle(s, pilot)


@pytest.mark.asyncio
async def test_r2_esc_during_cleanup_window_cancels_worker(app):
    """m-F: jendela cleanup M3 (busy sudah False, worker masih membongkar
    UI) — Esc tetap mengonsumsi + cancel worker (syarat `session.busy`
    dulu terlalu ketat). Cancel kedua di tengah cleanup aman (M2)."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s._agent_ctl = StubController(s.session)
        await _submit(s, pilot, "cari sesuatu")
        chat = s.query_one(ChatPanel)
        for _ in range(100):
            await pilot.pause()
            if "c1" in chat._tool_rows and s.session.busy:
                break
        orig_info = chat.add_info

        async def slow_info(text: str) -> None:
            await asyncio.sleep(0.5)
            await orig_info(text)

        chat.add_info = slow_info
        await pilot.press("escape")  # cancel #1 (turn aktif)
        for _ in range(100):
            await pilot.pause()
            if not s.session.busy and s._turn_worker is not None:
                break
        assert not s.session.busy and s._turn_worker is not None

        worker = s._turn_worker
        assert s._on_escape() is True  # Esc #2: consumed (dulu no-op)
        assert worker.is_cancelled
        await _settle_idle(s, pilot)
        assert s._turn_worker is None
        assert worker.is_finished
        assert app.screen is s
        assert _cancel_msgs(chat) <= 1  # toast cancel tak dobel


# ------------------------------- ronde-3 delta (audit final: MAJOR-2 + MINOR)


@pytest.mark.asyncio
async def test_r3_live_burst_one_widget_ordered(app):
    """MAJOR-2: dua baris live bareng utk call_id sama → tepat 1 widget
    .live-out, urutan baris terjaga. Dulu: race add_live_output — dua
    burst sama-sama lihat entry None → dobel-mount, widget pertama yatim
    permanen (drop pop cuma satu) + urutan baris bisa tertukar."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        chat = s.query_one(ChatPanel)
        await chat.add_tool_row("c9", "bash", {})
        await asyncio.gather(chat.add_live_output("c9", "a1"),
                             chat.add_live_output("c9", "a2"))
        await pilot.pause()
        lives = list(chat.query(".live-out"))
        assert len(lives) == 1, lives
        lines = _plain(lives[0]).splitlines()
        assert lines == ["a1", "a2"], lines


@pytest.mark.asyncio
async def test_r3_live_after_tool_done_stays_silent(app):
    """MINOR-3: baris telat pasca-AgentToolDone jangan hidupkan lagi blok
    live — guard `_tool_rows` saja kurang (row done masih terdaftar),
    cabang create jalan → blok live baru muncul di bawah row selesai."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        chat = s.query_one(ChatPanel)
        await chat.add_tool_row("c8", "bash", {})
        await chat.add_live_output("c8", "jalan")
        assert "c8" in chat._live
        # alur _emit AgentToolDone: drop dulu, baru update row
        await chat.drop_live_output("c8")
        await chat.update_tool_row("c8", "bash", True, {"success": True})
        n = len(chat.children)
        await chat.add_live_output("c8", "telat dari thread")
        assert len(chat.children) == n, "blok live baru tak boleh muncul"
        assert "c8" not in chat._live


@pytest.mark.asyncio
async def test_r3_esc_inside_popup_palette_wins(app):
    """MINOR-2: fokus DI DALAM popup (ask() fokus ke perm-yes) + palette
    terbuka → Esc tutup palette DULU via rantai _on_escape; popup TIDAK
    dijawab (dulu PermissionPopup.on_key handle escape sendiri → jawab
    "no" walau palette terbuka — inversi prioritas)."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        ctl = StubControllerPerm(s.session)
        s._agent_ctl = ctl
        await _submit(s, pilot, "tulis file")
        perm = s.query_one(PermissionPopup)
        for _ in range(100):
            await pilot.pause()
            if perm.is_waiting and s.session.busy:
                break
        assert perm.is_waiting
        assert isinstance(app.focused, Button)  # fokus di dalam popup
        s.action_open_palette()
        for _ in range(2):
            await pilot.pause()
        pal = s.query_one(SlashPalette)
        assert pal.overlay_open
        await pilot.press("escape")
        for _ in range(3):
            await pilot.pause()
        assert not pal.display  # Esc #1: palette ditutup dulu
        assert perm.is_waiting  # popup BELUM terjawab
        assert ctl.answer is None
        await pilot.press("escape")  # Esc #2: sekarang jawab izin
        for _ in range(3):
            await pilot.pause()
        assert not perm.is_waiting
        await _settle_idle(s, pilot)
        assert ctl.answer == "no"  # semantics Esc = no tetap utuh


@pytest.mark.asyncio
async def test_r3_footer_reset_survives_inbar_raise(app):
    """MINOR-4: finally _run_turn suppress per-statement — inbar
    .set_busy(False) raise jangan skip reset footer (footer nyangkut
    'esc batalkan' selamanya)."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        orig = InputBar.set_busy

        def flaky(self, busy: bool) -> None:
            if not busy:
                raise RuntimeError("probe MINOR-4")
            orig(self, busy)

        InputBar.set_busy = flaky  # type: ignore[method-assign]
        try:
            class QuickCtl:
                def __init__(self, session: SessionState) -> None:
                    self.session = session

                async def run_turn(self, text, hooks, active_tools=None):
                    self.session.begin_turn()
                    try:
                        await hooks.emit(AgentToolStart(
                            "c7", "bash", {"command": "x"}))
                        await hooks.emit(AgentToolDone(
                            "c7", "bash", True, {"success": True}))
                        await hooks.emit(AgentText("selesai"))
                    finally:
                        self.session.end_turn()

            s._agent_ctl = QuickCtl(s.session)
            await _submit(s, pilot, "cepat")
            for _ in range(200):
                await pilot.pause()
                if not s.session.busy and s._turn_worker is None:
                    break
            assert not s.session.busy and s._turn_worker is None
            # Kunci MINOR-4: footer ikut di-reset walau inbar raise.
            assert s.query_one(FooterBar)._busy is False
            assert "esc batalkan" not in _plain(s.query_one(FooterBar))
        finally:
            InputBar.set_busy = orig  # type: ignore[method-assign]
