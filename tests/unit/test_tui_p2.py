"""Unit: P2 esc interrupt (issue #56) — cancel turn jalan + hint footer."""

from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("MULTACD_HOME", "/tmp/opencode/test-p2")

from core.agent_events import (
    AgentText,
    AgentToolDone,
    AgentToolStart,
)
from core.config import Config
from core.session_state import SessionState
from tui.app import MultacdApp
from tui.widgets.chat_panel import ChatPanel
from tui.widgets.footer_bar import (
    BUSY_HINT,
    FooterBar,
    render_footer,
    short_workdir,
)
from tui.widgets.input_bar import InputBar
from tui.widgets.model_selector import ModelSelector
from tui.widgets.permission_popup import PermissionPopup
from tui.widgets.slash_palette import SlashPalette


def _plain(widget) -> str:
    """Teks polos widget (Text/Content) — aman gagal render."""
    try:
        r = widget.render()
        return str(getattr(r, "plain", r))
    except Exception:
        return ""


class StubController:
    """Controller stub: emit tool row lalu ngambang — jendela cancel.

    Sengaja tanpa LLM nyata: cukup buat prove UI-layer cancel (P2).
    """

    def __init__(self, session: SessionState) -> None:
        self.session = session

    async def run_turn(self, text, hooks, active_tools=None):
        self.session.begin_turn()
        try:
            await hooks.emit(AgentToolStart(
                "c1", "bash", {"command": "sleep 5"}))
            await asyncio.sleep(5)  # jendela cancel
            await hooks.emit(AgentToolDone(
                "c1", "bash", True, {"success": True}))
        finally:
            self.session.end_turn()


@pytest.fixture()
def app():
    return MultacdApp(Config(model="groq/llama-3.3-70b", api_key="k"))


async def _open_main(app, pilot):
    """Pop FreshScreen + sinkron beberapa frame."""
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


@pytest.mark.asyncio
async def test_esc_cancels_turn_and_marks_tool(app):
    """Esc saat turn jalan → worker cancel, session idle, row + pesan jujur."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s._agent_ctl = StubController(s.session)
        await _submit(s, pilot, "cari sesuatu")
        chat = s.query_one(ChatPanel)
        for _ in range(100):
            await pilot.pause()
            if "c1" in chat._tool_rows and s.session.busy:
                break
        assert s.session.busy and s._live_call == "c1"
        foot = s.query_one(FooterBar)
        assert foot._busy is True  # hint 'esc batalkan' aktif
        assert "esc batalkan" in _plain(foot)

        await pilot.press("escape")
        await _settle_idle(s, pilot)  # flake: busy False < footer reset
        assert s._turn_worker is None  # ref dibersihkan di finally
        assert chat._tool_rows["c1"]._cancelled  # row running → cancelled
        assert any("dibatalkan" in _plain(w) for w in chat.children)
        assert foot._busy is False
        assert not s.session.busy  # guard _submit lepas → bisa submit lagi


@pytest.mark.asyncio
async def test_esc_palette_wins_over_cancel(app):
    """Prioritas Esc: palette terbuka saat busy → tutup palette dulu."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s._agent_ctl = StubController(s.session)
        await _submit(s, pilot, "cari sesuatu")
        await _wait_busy(s, pilot, want=True)
        s.action_open_palette()  # Ctrl+P overlay saat turn jalan
        for _ in range(2):
            await pilot.pause()
        pal = s.query_one(SlashPalette)
        assert pal.overlay_open
        await pilot.press("escape")
        for _ in range(3):
            await pilot.pause()
        assert not pal.display  # Esc #1: palette ditutup
        assert s.session.busy   # turn TIDAK ikut dibatalkan
        await pilot.press("escape")
        await _wait_busy(s, pilot, want=False)
        assert not s.session.busy  # Esc #2: barusan cancel turn


@pytest.mark.asyncio
async def test_esc_idle_is_noop(app):
    """Esc saat idle: tidak cancel apa pun, app tetap hidup, tak keluar."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        inp = s.query_one("#input-bar", InputBar)
        inp.focus()
        await pilot.press("escape")
        for _ in range(3):
            await pilot.pause()
        assert not s.session.busy
        assert s._turn_worker is None
        assert app.screen is s  # masih di MainScreen (no-op, bukan quit)


# ---------------------------------------------------------------------------
# Edge case QA (issue #56): perilaku di luar tes inti coder.


class StubControllerStream:
    """Pure streaming tanpa tool — _live_call tetap None (edge #5)."""

    def __init__(self, session: SessionState) -> None:
        self.session = session

    async def run_turn(self, text, hooks, active_tools=None):
        self.session.begin_turn()
        try:
            await hooks.emit(AgentText("halo "))
            await asyncio.sleep(5)  # jendela cancel tanpa tool row
            await hooks.emit(AgentText("dunia"))
        finally:
            self.session.end_turn()


class StubControllerPerm:
    """confirm() → popup waiting; setelah dijawab 'no' turn lanjut (edge #2)."""

    def __init__(self, session: SessionState) -> None:
        self.session = session
        self.answer: str | None = None

    async def run_turn(self, text, hooks, active_tools=None):
        self.session.begin_turn()
        try:
            self.answer = await hooks.confirm(
                "write_file", {"path": "a.py"})
            await hooks.emit(AgentText(f"answered:{self.answer}"))
            await asyncio.sleep(0.5)  # jendela: Esc tak boleh cancel
        finally:
            self.session.end_turn()


class StubControllerQuick:
    """Turn ke-2 lengkap + cepat (edge #3): tool start→done + teks."""

    def __init__(self, session: SessionState) -> None:
        self.session = session

    async def run_turn(self, text, hooks, active_tools=None):
        self.session.begin_turn()
        try:
            await hooks.emit(AgentToolStart(
                "c2", "bash", {"command": "echo hi"}))
            await hooks.emit(AgentToolDone(
                "c2", "bash", True, {"success": True}))
            await hooks.emit(AgentText("selesai dua"))
            await asyncio.sleep(0.5)  # jendela observasi turn 2
        finally:
            self.session.end_turn()


def _cancel_msgs(chat: ChatPanel) -> int:
    """Jumlah info 'dibatalkan' di chat — guard duplikat/hilang."""
    return sum("dibatalkan" in _plain(w) for w in chat.children)


async def _settle_idle(s, pilot, tries: int = 100) -> None:
    """Tunggu UI benar-benar idle: busy False + ref worker bersih +
    footer reset (set_busy(False) jalan SETELAH await close_assistant —
    cek busy saja terlalu awal, race)."""
    foot = s.query_one(FooterBar)
    for _ in range(tries):
        await pilot.pause()
        if (not s.session.busy and s._turn_worker is None
                and foot._busy is False):
            return
    raise AssertionError("UI tak settle ke idle")


@pytest.mark.asyncio
async def test_esc_twice_rapid_stays_clean(app):
    """Edge #1: Esc dua kali cepat saat busy → tak crash, idle bersih."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s._agent_ctl = StubController(s.session)
        await _submit(s, pilot, "cari sesuatu")
        chat = s.query_one(ChatPanel)
        for _ in range(100):
            await pilot.pause()
            if "c1" in chat._tool_rows and s.session.busy:
                break
        assert s.session.busy and s._live_call == "c1"

        await pilot.press("escape", "escape")  # dua kali, tanpa jeda
        await _settle_idle(s, pilot)
        await pilot.pause()
        # state akhir bersih apapun interleaving cancel-nya:
        assert not s.session.busy
        assert s._turn_worker is None
        assert s._live_call is None
        assert s._bg_active is False
        assert s.query_one(FooterBar)._busy is False
        assert chat._tool_rows["c1"]._cancelled  # cancel pertama menang
        assert _cancel_msgs(chat) <= 1  # tak boleh dobel toast
        assert app.screen is s  # app tetap hidup, tak keluar

        await pilot.press("escape")  # Esc tambahan saat idle: no-op lagi
        for _ in range(3):
            await pilot.pause()
        assert app.screen is s and not s.session.busy


@pytest.mark.asyncio
async def test_esc_permission_popup_answers_no_not_cancel(app):
    """Edge #2: Esc saat popup izin waiting → jawab 'no', turn lanjut."""
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
        assert perm.is_waiting and s.session.busy

        await pilot.press("escape")
        for _ in range(3):
            await pilot.pause()
        assert not perm.is_waiting  # popup terjawab…
        assert perm.display is False
        assert s.session.busy and s._turn_worker is not None  # …turn UTUH

        await _settle_idle(s, pilot)
        assert ctl.answer == "no"  # semantics lama: Esc = no
        chat = s.query_one(ChatPanel)
        assert _cancel_msgs(chat) == 0
        # stream SETELAH Esc tetap masuk (turn utuh):
        assert "answered:no" in " ".join(chat._assistant_history)
        assert s.query_one(FooterBar)._busy is False


@pytest.mark.asyncio
async def test_cancel_then_submit_second_turn_normal(app):
    """Edge #3: cancel → submit baru: worker ref di-set ulang, footer balik."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s._agent_ctl = StubController(s.session)
        await _submit(s, pilot, "pertama")
        chat = s.query_one(ChatPanel)
        for _ in range(100):
            await pilot.pause()
            if "c1" in chat._tool_rows and s.session.busy:
                break
        await pilot.press("escape")
        await _settle_idle(s, pilot)
        assert _cancel_msgs(chat) == 1

        # submit kedua harus lolos guard dan jalan normal:
        s._agent_ctl = StubControllerQuick(s.session)
        await _submit(s, pilot, "kedua")
        assert s._turn_worker is not None  # ref lama dibersihkan, baru dipasang
        await _wait_busy(s, pilot, want=True)
        foot = s.query_one(FooterBar)
        assert foot._busy is True and "esc batalkan" in _plain(foot)
        assert s.query_one(InputBar).disabled is True  # guard aktif lagi

        await _settle_idle(s, pilot)
        assert chat._tool_rows["c2"]._done
        assert not chat._tool_rows["c2"]._cancelled  # selesai natural
        assert _cancel_msgs(chat) == 1  # tak ada pesan cancel baru
        assert s._turn_worker is None and foot._busy is False
        assert "esc batalkan" not in _plain(foot)  # hint balik normal
        assert "kedua" in " ".join(_plain(w) for w in chat.children)


@pytest.mark.asyncio
async def test_esc_while_backgrounded_cancels_clean(app):
    """Edge #4: Ctrl+B lalu Esc → tetap cancel beneran, state rapi."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s._agent_ctl = StubController(s.session)
        await _submit(s, pilot, "cari sesuatu")
        chat = s.query_one(ChatPanel)
        for _ in range(100):
            await pilot.pause()
            if "c1" in chat._tool_rows and s.session.busy:
                break
        s.action_background_task()  # Ctrl+B (binding — sama jalurnya)
        for _ in range(3):
            await pilot.pause()
        assert s._bg_active is True and s.session.busy  # bg bukan cancel

        await pilot.press("escape")
        await _settle_idle(s, pilot)
        assert s._bg_active is False  # finally reset mode UI
        assert s._turn_worker is None
        assert chat._tool_rows["c1"]._cancelled
        assert _cancel_msgs(chat) == 1  # tool masih live → pesan jujur muncul
        texts = " ".join(_plain(w) for w in chat.children)
        assert "Background selesai" not in texts  # cancel ≠ selesai (P2)
        foot = s.query_one(FooterBar)
        assert foot._busy is False and "esc batalkan" not in _plain(foot)
        assert app.screen is s


@pytest.mark.asyncio
async def test_esc_pure_stream_still_reports_cancel(app):
    """M1 (issue #56): cancel pure streaming TETAP ada info 'dibatalkan'.

    Dulu bubble ditutup seolah normal (nol umpan balik) — sekarang selalu
    ada pesan cancel; tanpa tool = tanpa kalimat tool-shell-background.
    """
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s._agent_ctl = StubControllerStream(s.session)
        await _submit(s, pilot, "cerita dong")
        chat = s.query_one(ChatPanel)
        for _ in range(100):
            await pilot.pause()
            if s.session.busy and "halo" in chat._assistant_text:
                break
        assert s._live_call is None  # murni streaming, tanpa tool
        assert "halo" in chat._assistant_text  # stream sempat jalan

        await pilot.press("escape")
        await _settle_idle(s, pilot)
        assert _cancel_msgs(chat) == 1  # jujur: selalu ada pesan dibatalkan
        assert chat._tool_rows == {}  # tak ada row tool → tanpa kalimat shell
        assert s._turn_worker is None and s._live_call is None
        foot = s.query_one(FooterBar)
        assert foot._busy is False
        assert app.screen is s and s.query_one(InputBar).disabled is False


# ----------------------------------------------------- footer busy (pure fn)


def test_render_footer_busy_one_short_line_compact():
    """Edge #6: busy=True → 1 baris pendek, hint binding diganti, compact-safe."""
    wd, use = "~/multacd", "12 · 345"
    busy = render_footer(wd, use, compact=True, busy=True)
    assert "\n" not in busy  # tetap 1 baris
    assert BUSY_HINT in busy
    assert "ctrl+" not in busy  # hint lain tak menyesatkan saat busy
    # compact/non-compact sama-sama pendek saat busy (satu hint terpendek):
    assert busy == render_footer(wd, use, compact=False, busy=True)
    idle = render_footer(wd, use, compact=False, busy=False)
    assert len(busy) < len(idle) and len(busy) <= 100
    # workdir maksimum (32 col) + usage lebar → tetap muat layar sempit:
    long = render_footer(short_workdir("/a" * 200), "999 · 999999", True, True)
    assert "\n" not in long and BUSY_HINT in long and len(long) <= 60


def test_footer_bar_set_busy_roundtrip():
    """Edge #6b: FooterBar.set_busy toggle — repaint aman sebelum mount."""
    bar = FooterBar.__new__(FooterBar)
    bar._workdir, bar._usage, bar._compact, bar._busy = "?", "—", False, False
    bar.set_busy(True)
    assert bar._busy is True  # tak raise walau belum mount
    bar.set_busy(False)
    assert bar._busy is False


# ------------------------------------------------- regresi audit (M2-M7)


class StubCounting:
    """Turn lambat + hitung panggilan (M3: submit dilarang saat cleanup)."""

    def __init__(self, session: SessionState, calls: list[str]) -> None:
        self.session = session
        self.calls = calls

    async def run_turn(self, text, hooks, active_tools=None):
        self.calls.append(text)
        cid = f"c{len(self.calls)}"  # call_id unik per turn (hindari dup id)
        self.session.begin_turn()
        try:
            await hooks.emit(AgentToolStart(
                cid, "bash", {"command": "sleep 5"}))
            await asyncio.sleep(5)  # jendela cancel
        finally:
            self.session.end_turn()


async def _wait_cleanup_started(s, pilot, flag: dict) -> None:
    """Tunggu sampai kosmetik cleanup mulai jalan (patch lambat)."""
    for _ in range(100):
        await pilot.pause()
        if flag["started"]:
            return
    raise AssertionError("cleanup kosmetik tak mulai")


async def _wait_window(s, pilot) -> None:
    """Tunggu jendela M3: busy sudah False, worker masih tercatat."""
    for _ in range(100):
        await pilot.pause()
        if not s.session.busy and s._turn_worker is not None:
            return
    raise AssertionError("jendela cleanup tak ketemu")


@pytest.mark.asyncio
async def test_m2_second_cancel_in_cleanup_keeps_input_alive(app):
    """M2: cancel kedua mendarat di await finally → state kritis tetap
    di-reset (input tidak mati permanen). Dulu: finally terpotong."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s._agent_ctl = StubController(s.session)
        await _submit(s, pilot, "cari sesuatu")
        chat = s.query_one(ChatPanel)
        for _ in range(100):
            await pilot.pause()
            if "c1" in chat._tool_rows and s.session.busy:
                break
        # kosmetik cleanup dibuat lambat → jendela cancel kedua pasti kena
        orig_close = chat.close_assistant
        flag = {"started": False}

        async def slow_close(meta: str = "") -> None:
            flag["started"] = True
            await asyncio.sleep(0.5)
            await orig_close(meta)

        chat.close_assistant = slow_close
        worker = s._turn_worker
        await pilot.press("escape")
        await _wait_cleanup_started(s, pilot, flag)
        worker.cancel()  # cancel kedua DI DALAM finally

        await _settle_idle(s, pilot)
        assert not s.session.busy  # end_turn tetap jalan (sync di depan)
        assert s._turn_worker is None
        assert s.query_one(InputBar).disabled is False  # input hidup
        assert s.query_one(FooterBar)._busy is False
        assert app.screen is s  # app tidak mati


@pytest.mark.asyncio
async def test_m3_submit_blocked_during_cancel_cleanup(app):
    """M3: klik tree/palette/export saat cleanup cancel → TIDAK menimpa
    turn (dulu guard cuma cek busy, jendela busy=False bisa ditembus)."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        calls: list[str] = []
        s._agent_ctl = StubCounting(s.session, calls)
        await _submit(s, pilot, "pertama")
        chat = s.query_one(ChatPanel)
        for _ in range(100):
            await pilot.pause()
            if "c1" in chat._tool_rows and s.session.busy:
                break
        # except-block cleanup dibuat lambat → jendela busy=False terbuka
        orig_info = chat.add_info
        flag = {"started": False}

        async def slow_info(text: str) -> None:
            flag["started"] = True
            await asyncio.sleep(0.5)
            await orig_info(text)

        chat.add_info = slow_info
        await pilot.press("escape")
        await _wait_window(s, pilot)
        ref = s._turn_worker
        s._submit("jangan lewat")  # jalur non-input (klik tree, dll.)
        assert s._turn_worker is ref  # tak menimpa worker lama
        await _settle_idle(s, pilot)
        assert calls == ["pertama"]  # turn kedua TIDAK jalan
        # setelah settle, guard terbuka lagi — submit normal lolos
        s._submit("kedua")
        for _ in range(20):
            await pilot.pause()
            if len(calls) > 1:
                break
        assert s._turn_worker is not None and calls[-1] == "kedua"
        await pilot.press("escape")
        await _settle_idle(s, pilot)


@pytest.mark.asyncio
async def test_m4_clear_is_tui_local_and_cleans_context(app):
    """M4: /clear TUI-local — context bersih + system diisi ulang, tanpa
    turn worker (dulu lewat worker; Esc di tengah nyisain chat terpotong)."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s.app.context.add_message("user", "pesan lama")
        s.app.context.add_message("assistant", "jawab lama")
        chat = s.query_one(ChatPanel)
        await chat.add_info("info lama")
        await _submit(s, pilot, "/clear")
        for _ in range(20):
            await pilot.pause()
        msgs = s.app.context.get_messages()
        assert [m["role"] for m in msgs] == ["system"]  # bersih + isi ulang
        assert msgs[0]["content"] == s.app.composer.compose()
        assert s._turn_worker is None  # tak lewat turn (tak bisa di-cancel)
        assert not s.session.busy
        texts = " ".join(_plain(w) for w in chat.children)
        assert "History dibersihkan" in texts
        assert "lama" not in texts  # bubble lama hilang
        assert chat._assistant_history == [] and chat._tool_rows == {}


@pytest.mark.asyncio
async def test_m5_late_live_output_dropped_after_cancel(app):
    """M5: baris telat dari thread tool setelah cancel → dibuang, tak
    bikin blok live yatim untuk call_id yang sudah di-drop."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s._agent_ctl = StubController(s.session)
        await _submit(s, pilot, "cari sesuatu")
        chat = s.query_one(ChatPanel)
        for _ in range(100):
            await pilot.pause()
            if "c1" in chat._tool_rows and s.session.busy:
                break
        s._queue_live("c1", "baris hidup")  # jalur normal saat turn jalan
        for _ in range(50):
            await pilot.pause()
            if "c1" in chat._live:
                break
        assert "baris hidup" in _plain(chat._live["c1"][0])

        await pilot.press("escape")
        await _settle_idle(s, pilot)
        n_children = len(chat.children)
        s._queue_live("c1", "telat dari thread")  # sinkron, tanpa await
        await pilot.pause()
        assert chat._live == {}  # tak ada widget live yatim
        assert len(chat.children) == n_children


@pytest.mark.asyncio
async def test_m7_esc_palette_wins_over_permission_from_input(app):
    """M7: input fokus + permission menunggu + palette terbuka → Esc
    menutup palette DULU (dulu: permission langsung dijawab 'no')."""
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
        # Ctrl+B: input usable lagi (bg mode) → InputBar bisa terima Esc
        s.action_background_task()
        for _ in range(2):
            await pilot.pause()
        s.query_one(InputBar).focus()
        s.action_open_palette()  # Ctrl+P overlay
        for _ in range(2):
            await pilot.pause()
        pal = s.query_one(SlashPalette)
        assert pal.overlay_open and perm.is_waiting

        await pilot.press("escape")
        for _ in range(3):
            await pilot.pause()
        assert not pal.display  # Esc #1: palette ditutup duluan
        assert perm.is_waiting  # izin BELUM dijawab
        assert ctl.answer is None  # jawaban "no" TIDAK terjadi di sini

        await pilot.press("escape")  # Esc #2: sekarang jawab izin
        for _ in range(3):
            await pilot.pause()
        assert not perm.is_waiting
        await _settle_idle(s, pilot)
        assert ctl.answer == "no"  # semantics lama Esc = no tetap utuh


@pytest.mark.asyncio
async def test_esc_closes_selector_when_focus_not_on_input(app):
    """Minor m1: selector terbuka + fokus di luar input → Esc tetap
    menutup selector (dulu no-op, selector nyangkut)."""
    async with app.run_test(size=(100, 30)) as pilot:
        s = await _open_main(app, pilot)
        s.model_open()  # buka ModelSelector
        for _ in range(2):
            await pilot.pause()
        sel = s.query_one(ModelSelector)
        assert sel.is_open
        s.query_one("#chat-panel").focus()  # fokus BUKAN input
        for _ in range(2):
            await pilot.pause()
        await pilot.press("escape")
        for _ in range(3):
            await pilot.pause()
        assert not sel.is_open  # ditutup screen (bukan no-op)
