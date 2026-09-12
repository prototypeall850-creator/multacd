"""Agent loop — ReAct: Reason → Act → Observe.

Menyambungkan LLM + tools + memory + permission jadi satu loop.
Async generator — setiap update di-yield real-time ke TUI:

    async for event in run_agent(user_input, context, config):
        isinstance(event, AgentText)      → tampilkan potongan teks
        isinstance(event, AgentToolStart) → tampilkan tool berjalan
        isinstance(event, AgentToolDone)  → update jadi sukses / gagal
        isinstance(event, AgentDone)      → agent selesai
        isinstance(event, AgentError)     → tampilkan error, loop berhenti

Konfirmasi & pertanyaan user di-inject sebagai callback async
(TUI memasang dialog; default fallback = stdin). Pola ini dipilih
agar agent_loop tidak tahu-menahu soal UI.

Test cepat (tanpa API key, pakai LLM fake):
    python -m core.agent_loop
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING, Any

from core.agent_events import (
    AgentContinue,
    AgentDone,
    AgentError,
    AgentEvent,
    AgentText,
    AgentToolDone,
    AgentToolStart,
    AgentUsage,
)
from core.config import Config
from core.llm_client import LLMClient, LLMError, StreamDone, StreamText, setup_client
from core.permissions import PermissionChecker
from memory.context import ConversationContext
from tools.common import fail
from tools.registry import execute_tool, get_tool_definitions

if TYPE_CHECKING:
    from core.mode_manager import ModeManager
    from core.prompt_composer import PromptComposer

SYSTEM_PROMPT = (
    "Kamu multacd, coding agent di terminal. Jawab dengan bahasa yang dipakai user "
    "(default: Indonesia santai). "
    "Gunakan tool yang tersedia untuk mengerjakan tugas — baca file dulu sebelum mengedit. "
    "Kalau hasil tool berisi 'Dibatalkan user', hormati itu: cari cara lain atau tanya user. "
    "Jangan panggil tool yang tidak ada di daftar. Jangan cetak JSON mentah ke user."
)
# Fallback kalau run_agent dipanggil tanpa composer (stdin/test).
# Jalur resmi TUI selalu oper composer (lihat tui/app.py + main_screen.py).

# confirm: "yes" | "no" | "all" (all = izinkan semua sesi ini)
ConfirmCallback = Callable[[str, dict[str, Any]], Awaitable[str]]
AskCallback = Callable[[str], Awaitable[str]]
# Live output tool: (call_id, baris). Dipanggil dari thread worker tool —
# TUI wajib marshal (call_from_thread); CLI boleh print langsung.
OutputCallback = Callable[[str, str], None]


# Re-export biar import lama (`from core.agent_loop import AgentText, ...`)
# tetap jalan selama migrasi (R2: tanpa ubah behavior).
__all__ = [
    "AgentContinue",
    "AgentDone",
    "AgentError",
    "AgentEvent",
    "AgentText",
    "AgentToolDone",
    "AgentToolStart",
    "AgentUsage",
    "run_agent",
]


def _stuck_error(tool_name: str) -> AgentError:
    """Pesan stagnan: tool+args sama gagal error-sama 3x beruntun."""
    return AgentError(
        f"`{tool_name}` gagal dengan error yang sama 3x beruntun — "
        "kemungkinan stuck. Coba pecah tugas jadi langkah kecil "
        "atau kasih instruksi lebih spesifik."
    )


async def _stdin_confirm(tool_name: str, params: dict[str, Any]) -> str:
    target = params.get("path") or params.get("command") or params.get("url") or ""
    extra = ""
    if tool_name == "git_commit":
        extra = "/e edit pesan"
    elif tool_name == "git_push":
        extra = "/b branch baru"
    print(f"[izin] {tool_name} {target} — lanjutkan? [y/n/a{extra}] ", end="", flush=True)
    try:
        ans = await asyncio.to_thread(input)
    except (EOFError, KeyboardInterrupt):
        return "no"
    ans = ans.strip()
    if ans in ("a", "all"):
        return "all"
    if ans in ("e", "edit") and tool_name == "git_commit":
        try:
            new_msg = await asyncio.to_thread(
                input, f"Pesan baru [{params.get('message', '')}]: ")
        except (EOFError, KeyboardInterrupt):
            return "no"
        return f"edit:{new_msg.strip() or params.get('message', '')}"
    if ans in ("b", "branch") and tool_name == "git_push":
        return "branch"
    return "yes" if ans in ("y", "yes") else "no"


async def _stdin_ask(question: str) -> str:
    print(f"? {question}")
    try:
        return await asyncio.to_thread(input, "Jawaban: ")
    except (EOFError, KeyboardInterrupt):
        return "(dibatalkan)"


async def run_agent(
    user_input: str,
    context: ConversationContext,
    config: Config,
    *,
    llm_client: LLMClient | None = None,
    confirm: ConfirmCallback | None = None,
    ask_user: AskCallback | None = None,
    mode_manager: ModeManager | None = None,
    active_tools: list[str] | None = None,
    composer: PromptComposer | None = None,
    output_cb: OutputCallback | None = None,
    continue_on_limit: bool = False,
    checker: PermissionChecker | None = None,
) -> AsyncIterator[AgentEvent]:
    """Jalankan satu turn agent. Yield AgentEvent secara real-time.

    Batas iterasi (ala opencode): tiap LLM round yang berisi tool call
    = 1 step. Capai limit → yield AgentContinue (bukan AgentError).
    TUI tanya user Lanjut/Berhenti; continue_on_limit=True (dipakai
    retry lanjutan) langsung lanjut tanpa tanya. Infinite loop nyata
    (LLM ngulang tool sama tanpa progres) tetap berhenti via deteksi
    stagnan di bawah.

    `checker` opsional biar pemilik sesi (AgentController) bisa pakai
    satu PermissionChecker lintas turn — approve [A] jadi beneran
    per-sesi, bukan hilang tiap turn (issue #32). Default None =
    checker baru per turn (perilaku lama, dipakai CLI/test).
    """
    def _system_prompt() -> str:
        return composer.compose() if composer is not None else SYSTEM_PROMPT

    # ── Slash command: intercept sebelum LLM, tidak masuk history ──
    if mode_manager is not None and mode_manager.is_command(user_input):
        result = mode_manager.handle_command(user_input)
        if result.action == "clear":
            context.clear()
            context.add_message("system", _system_prompt())
        yield AgentText(result.message)
        yield AgentDone(result.message)
        return

    llm = llm_client or setup_client(config)
    checker = checker or PermissionChecker(config)
    confirm_cb = confirm or _stdin_confirm
    ask_cb = ask_user or _stdin_ask
    defs = get_tool_definitions()
    # Bukan git repo → tool git disembunyikan dari LLM (lihat ModeManager).
    # Tool plugin selalu ikut (user-extension tersedia di semua mode).
    if active_tools is None:
        tools = defs
    else:
        from tools.registry import plugin_tool_names
        allowed = set(active_tools) | set(plugin_tool_names())
        tools = [d for d in defs if d["function"]["name"] in allowed]

    if not context.get_messages():
        context.add_message("system", _system_prompt())
    elif composer is not None:
        # #26: mode ganti → composer baru, tapi history masih bawa
        # system lama. Refresh tiap turn (ala opencode: system disusun
        # ulang tiap request) biar LLM baca persona yang benar.
        context.set_system(_system_prompt())
    context.add_message("user", user_input)

    iteration = 0
    tool_rounds = 0  # round LLM yang berisi tool call (step ala opencode)
    recent_names: list[str] = []  # nama tool terakhir (ringkasan Continue)
    recent_fails: list[tuple[str, str, str]] = []  # (nama, args, err) stagnan

    def _track_outcome(name: str, args: dict[str, Any],
                       res: dict[str, Any]) -> bool:
        """Catat hasil tool. True = stagnan: tool+args yang sama gagal
        dengan error yang sama 3x beruntun (tanpa progres). Sukses atau
        error yang beda = progres, tidak dihitung. Issue #28."""
        import json as _js
        try:
            sig = _js.dumps(args, sort_keys=True, ensure_ascii=False,
                            default=str)
        except Exception:
            sig = ""
        err = str(res.get("error") or "").splitlines()
        recent_fails.append((name, sig, err[0][:120] if err else ""))
        if len(recent_fails) < 3:
            return False
        a, b, c = recent_fails[-3:]
        return (a[0] == b[0] == c[0] and a[1] == b[1] == c[1]
                and bool(a[2]) and a[2] == b[2] == c[2])
    while True:
        iteration += 1
        if iteration > config.max_tool_iterations and not continue_on_limit:
            # Limit = proteksi, bukan vonis. Kasih user pilihan lanjut —
            # opencode juga begini (lanjut tanpa reset konteks).
            summary = ", ".join(recent_names[-3:]) or "(belum ada tool)"
            yield AgentContinue(
                tool_count=tool_rounds,
                limit=config.max_tool_iterations,
                summary=f"Batas {config.max_tool_iterations} iterasi tercapai "
                        f"({tool_rounds} tool call: {summary}). "
                        "Pilih Lanjut buat terusin, Berhenti buat sudahi.",
            )
            return
        if iteration > config.max_tool_iterations * 3:
            # Safety net absolut: 3x limit tanpa selesai = loop beneran.
            yield AgentError(
                f"Berhenti setelah {config.max_tool_iterations * 3} iterasi "
                "tanpa selesai — kemungkinan infinite loop. "
                "Coba pecah tugas jadi langkah kecil."
            )
            return

        # ── Reason: tanya LLM (streaming, teks langsung di-yield) ──
        try:
            done: StreamDone | None = None
            async for event in llm.stream_completion(context.get_messages(), tools):
                if isinstance(event, StreamText):
                    if event.content:
                        yield AgentText(event.content)
                elif isinstance(event, StreamDone):
                    done = event
                    yield AgentUsage(done.prompt_tokens, done.completion_tokens)
            if done is None:
                # Provider aneh: stream tutup tanpa StreamDone — jangan
                # biarkan assert mentah, kasih pesan yang bisa dibaca user.
                yield AgentError(
                    "Provider menutup stream tanpa hasil lengkap. "
                    "Coba ulangi; kalau berulang, cek status provider / model.")
                return
        except LLMError as e:
            yield AgentError(str(e))
            return

        context.add_assistant_tool_calls(done.text, done.tool_calls)

        if not done.tool_calls:
            yield AgentDone(done.text)
            return

        tool_rounds += 1

        # ── Act + Observe: proses tiap tool call ──
        for call in done.tool_calls:
            yield AgentToolStart(call.id, call.name, call.arguments)
            recent_names.append(call.name)

            # Tool "ask" dicegat: jawab via callback, bukan execute_tool (stdin).
            if call.name == "ask":
                question = call.arguments.get("question", "...")
                answer = await ask_cb(str(question))
                ask_result = {"success": True, "result": answer, "error": None}
                context.add_tool_result(call.id, "ask", ask_result)
                yield AgentToolDone(call.id, "ask", True, ask_result)
                _track_outcome("ask", call.arguments, ask_result)
                continue

            decision = checker.check(call.name, call.arguments)
            if decision == "deny":
                deny_result = fail(
                    f"Tool `{call.name}` tidak tersedia. Pakai tool dari daftar yang ada.")
                context.add_tool_result(call.id, call.name, deny_result)
                yield AgentToolDone(call.id, call.name, False, deny_result)
                if _track_outcome(call.name, call.arguments, deny_result):
                    yield _stuck_error(call.name)
                    return
                continue

            if decision == "ask":
                choice = await confirm_cb(call.name, call.arguments)
                if choice == "all":
                    checker.approve_all_for_session(call.name)
                    choice = "yes"
                # #4: user edit pesan commit → pakai pesan baru, lanjut yes.
                if choice.startswith("edit:"):
                    new_msg = choice[len("edit:"):].strip()
                    if not new_msg:
                        choice = "no"  # edit dibatalkan = tolak
                    elif "message" in call.arguments:
                        call.arguments["message"] = new_msg
                        choice = "yes"
                    else:
                        choice = "yes"
                # #4: user pilih buat branch baru (push protected) → buat
                # branch, arahkan push ke sana, lanjut yes.
                if choice == "branch":
                    new_branch = (await ask_cb(
                        "Nama branch baru buat push (kosongkan = batal)?"
                    ) or "").strip()
                    if not new_branch:
                        choice = "no"
                    else:
                        made = await asyncio.to_thread(
                            execute_tool, "git_checkout",
                            {"workdir": call.arguments.get("workdir", "."),
                             "branch": new_branch, "create": True})
                        if not made.get("success"):
                            context.add_tool_result(call.id, call.name, made)
                            yield AgentToolDone(call.id, call.name, False, made)
                            if _track_outcome(call.name, call.arguments, made):
                                yield _stuck_error(call.name)
                                return
                            continue
                        call.arguments["branch"] = new_branch
                        call.arguments.pop("allow_protected", None)
                        choice = "yes"
                if choice != "yes":
                    cancel_result = fail(
                        f"Dibatalkan user — jangan coba {call.name} yang sama lagi, "
                        "cari cara lain atau tanya user.")
                    context.add_tool_result(call.id, call.name, cancel_result)
                    yield AgentToolDone(call.id, call.name, False, cancel_result)
                    if _track_outcome(call.name, call.arguments, cancel_result):
                        yield _stuck_error(call.name)
                        return
                    continue

            # to_thread: tool sync jalan di thread, event loop tetap hidup.
            # Tanpa ini, tool research (yang emit event via call_from_thread)
            # deadlock — loop diblok nunggu thread, thread nunggu loop.
            # output_cb (live stream) jalan dari thread itu juga.
            def _live(line: str, _cid: str = call.id) -> None:
                assert output_cb is not None
                output_cb(_cid, line)
            result = await asyncio.to_thread(
                execute_tool, call.name, call.arguments,
                _live if output_cb is not None else None)
            context.add_tool_result(call.id, call.name, result)
            yield AgentToolDone(call.id, call.name, result["success"], result)
            if _track_outcome(call.name, call.arguments, result):
                yield _stuck_error(call.name)
                return


if __name__ == "__main__":
    import asyncio as _asyncio

    from core.llm_client import ToolCallRequest as _TCR

    class FakeLLM:
        """LLM scripted: antrean StreamDone, teksnya di-stream per kata."""

        def __init__(self, script: list[StreamDone]) -> None:
            self.script = list(script)
            self.seen_messages: list[list[dict]] = []

        async def stream_completion(self, messages, tools=None):
            self.seen_messages.append(messages)
            done = self.script.pop(0)
            for word in done.text.split():
                yield StreamText(word + " ")
            yield done

    async def _drain(gen):
        return [e async for e in gen]

    async def main() -> None:
        cfg = Config(model="m", api_key="k")

        # 1. Teks murni tanpa tool
        fake = FakeLLM([StreamDone("halo dunia", [])])
        ctx = ConversationContext()
        events = await _drain(run_agent("hi", ctx, cfg, llm_client=fake))
        assert isinstance(events[-1], AgentDone) and "halo" in events[-1].text, events
        assert sum(isinstance(e, AgentText) for e in events) == 2
        roles = [m["role"] for m in ctx.get_messages()]
        assert roles == ["system", "user", "assistant"], roles

        # 2. Tool auto (list_dir) jalan sendiri, lalu selesai
        fake = FakeLLM([
            StreamDone("cek dulu ", [_TCR("c1", "list_dir", {"path": "."})]),
            StreamDone("oke", []),
        ])
        ctx = ConversationContext()
        events = await _drain(run_agent("ls", ctx, cfg, llm_client=fake,
                                        confirm=_no_confirm))
        kinds = [type(e).__name__ for e in events]
        assert kinds == ["AgentText", "AgentText", "AgentUsage", "AgentToolStart",
                         "AgentToolDone", "AgentText", "AgentUsage",
                         "AgentDone"], kinds
        assert events[4].success is True
        tool_msgs = [m for m in ctx.get_messages() if m["role"] == "tool"]
        assert len(tool_msgs) == 1 and tool_msgs[0]["tool_call_id"] == "c1"
        # assistant message membawa tool_calls format OpenAI
        asst = [m for m in ctx.get_messages() if m.get("tool_calls")]
        assert asst and asst[0]["tool_calls"][0]["function"]["name"] == "list_dir"

        # 3. Tool ask (write_file) ditolak → tidak dieksekusi
        async def _deny(name, params):
            return "no"

        fake = FakeLLM([
            StreamDone("", [_TCR("c1", "write_file", {"path": "x.txt", "content": "x"})]),
            StreamDone("baiklah", []),
        ])
        ctx = ConversationContext()
        events = await _drain(run_agent("tulis", ctx, cfg, llm_client=fake, confirm=_deny))
        assert events[1].name == "write_file" and events[2].success is False
        assert "Dibatalkan user" in ctx.get_messages()[-2]["content"]

        # 4. "all" = sesi ini auto seterusnya
        answers = iter(["all"])

        async def _all(name, params):
            return next(answers)

        fake = FakeLLM([
            StreamDone("", [_TCR("c1", "bash", {"command": "echo a"})]),
            StreamDone("", [_TCR("c2", "bash", {"command": "echo b"})]),
            StreamDone("selesai", []),
        ])
        ctx = ConversationContext()
        events = await _drain(run_agent("run", ctx, cfg, llm_client=fake, confirm=_all))
        dones = [e for e in events if isinstance(e, AgentToolDone)]
        assert [d.success for d in dones] == [True, True], dones

        # 5. Tool halusinasi → deny, loop lanjut
        fake = FakeLLM([
            StreamDone("", [_TCR("c1", "hancurkan_semua", {})]),
            StreamDone("maaf", []),
        ])
        ctx = ConversationContext()
        events = await _drain(run_agent("x", ctx, cfg, llm_client=fake, confirm=_no_confirm))
        assert events[2].success is False
        assert "tidak tersedia" in ctx.get_messages()[-2]["content"]
        assert isinstance(events[-1], AgentDone)

        # 6. Limit → AgentContinue (bukan error): user bisa lanjut.
        # continue_on_limit=True = lanjutan tanpa tanya (dipakai TUI).
        # NOTE: jangan import ulang core.agent_loop di sini (double-import
        # trap python -m: kelas ganda, isinstance gagal). Pakai nama lokal.
        cfg2 = Config(model="m", api_key="k", max_tool_iterations=3)
        fake = FakeLLM([StreamDone("", [_TCR("c9", "list_dir", {})])] * 10)
        ctx = ConversationContext()
        events = await _drain(run_agent("loop", ctx, cfg2, llm_client=fake,
                                        confirm=_no_confirm))
        assert isinstance(events[-1], AgentContinue), events[-1]
        assert events[-1].limit == 3 and events[-1].tool_count == 3
        assert "list_dir" in events[-1].summary
        # Lanjutan: konteks utuh, loop terus sampai LLM selesai.
        # 5 tool (< 3x limit=9) lalu selesai → AgentDone, bukan safety net.
        fake = FakeLLM([StreamDone("", [_TCR("c9", "list_dir", {})])] * 5
                       + [StreamDone("akhirnya selesai", [])])
        ctx = ConversationContext()
        events = await _drain(run_agent("loop", ctx, cfg2, llm_client=fake,
                                        confirm=_no_confirm,
                                        continue_on_limit=True))
        assert isinstance(events[-1], AgentDone), events[-1]
        assert "selesai" in events[-1].text
        # Safety net absolut: 3x limit tanpa selesai = error beneran.
        # Pakai call SUKSES berulang (stagnan cuma bunuh gagal-sama-3x).
        fake = FakeLLM([StreamDone("", [_TCR("c9", "list_dir", {})])] * 100)
        ctx = ConversationContext()
        events = await _drain(run_agent("loop", ctx, cfg2, llm_client=fake,
                                        confirm=_no_confirm,
                                        continue_on_limit=True))
        assert isinstance(events[-1], AgentError), events[-1]
        assert "9 iterasi" in events[-1].message

        # 6b. Stagnan: tool+args sama GAGAL error-sama 3x → setop.
        # Sukses berulang = progres (retry), tidak dihitung.
        cfg3 = Config(model="m", api_key="k", max_tool_iterations=20)
        fake = FakeLLM([StreamDone("", [_TCR("c1", "read_file",
                                            {"path": "a.py"})])] * 5)
        ctx = ConversationContext()
        events = await _drain(run_agent("stuck", ctx, cfg3, llm_client=fake,
                                        confirm=_no_confirm))
        assert isinstance(events[-1], AgentError), events[-1]
        assert "3x" in events[-1].message and "read_file" in events[-1].message
        # Sukses-sama 3x = bukan stagnan (dibuktikan skenario 6 lanjutan).

        # 7. Tool ask() dicegat via callback (tanpa stdin)
        async def _answer(q):
            assert "nama" in q
            return "budi"

        fake = FakeLLM([
            StreamDone("", [_TCR("c1", "ask", {"question": "siapa nama?"})]),
            StreamDone("hai budi", []),
        ])
        ctx = ConversationContext()
        events = await _drain(run_agent("tanya", ctx, cfg, llm_client=fake,
                                        confirm=_no_confirm, ask_user=_answer))
        assert events[2].success is True
        assert "budi" in ctx.get_messages()[-2]["content"]

        # 8. Slash command dicegat — LLM tidak dipanggil, history bersih
        from core.mode_manager import ModeManager as _MM
        cfg_cmd = Config(model="m", api_key="k")
        mm = _MM(config=cfg_cmd)
        fake_empty = FakeLLM([])  # script kosong → error kalau LLM dipanggil
        ctx = ConversationContext()
        events = await _drain(run_agent("/help", ctx, cfg_cmd,
                                        llm_client=fake_empty, mode_manager=mm))
        assert isinstance(events[-1], AgentDone) and "/code" in events[-1].text
        assert ctx.get_messages() == [], ctx.get_messages()  # command tak masuk history
        # /clear mengosongkan history lalu isi ulang system prompt
        ctx.add_message("user", "x")
        events = await _drain(run_agent("/clear", ctx, cfg_cmd,
                                        llm_client=fake_empty, mode_manager=mm))
        assert [m["role"] for m in ctx.get_messages()] == ["system"]
        # /model ganti model on-the-fly
        events = await _drain(run_agent("/model openai/gpt-4o", ctx, cfg_cmd,
                                        llm_client=fake_empty, mode_manager=mm))
        assert cfg_cmd.model == "openai/gpt-4o" and "gpt-4o" in events[-1].text
        # bukan command → tetap ke LLM seperti biasa
        fake2 = FakeLLM([StreamDone("ok", [])])
        events = await _drain(run_agent("halo", ctx, cfg_cmd,
                                        llm_client=fake2, mode_manager=mm))
        assert isinstance(events[-1], AgentDone) and "ok" in events[-1].text

        # 9. active_tools memfilter definisi tool yang dilihat LLM
        seen_tools: list = []

        class RecLLM(FakeLLM):
            async def stream_completion(self, messages, tools=None):
                seen_tools.extend(t["function"]["name"] for t in (tools or []))
                async for e in super().stream_completion(messages, tools):
                    yield e

        fake3 = RecLLM([StreamDone("ok", [])])
        ctx = ConversationContext()
        await _drain(run_agent("hi", ctx, cfg_cmd, llm_client=fake3,
                               active_tools=["list_dir", "bash"]))
        assert seen_tools == ["list_dir", "bash"], seen_tools

        # 10. Composer → system message tersusun soul → ctx → mode → rules
        from core.prompt_composer import PromptComposer as _PC
        pc = _PC(soul="SOULKU")
        pc.update_project_ctx("CTXKU")
        pc.update_mode("MODEKU")
        fake4 = FakeLLM([StreamDone("ok", [])])
        ctx = ConversationContext()
        await _drain(run_agent("hi", ctx, cfg_cmd, llm_client=fake4, composer=pc))
        sys_msg = ctx.get_messages()[0]
        assert sys_msg["role"] == "system", sys_msg
        idx = [sys_msg["content"].index(x)
               for x in ("SOULKU", "CTXKU", "MODEKU", "Operational rules")]
        assert idx == sorted(idx), sys_msg["content"][:200]
        # /clear isi ulang dengan prompt tersusun, bukan hardcoded
        mm2 = _MM(config=cfg_cmd)
        await _drain(run_agent("/clear", ctx, cfg_cmd, llm_client=FakeLLM([]),
                               mode_manager=mm2, composer=pc))
        assert ctx.get_messages()[0]["content"].startswith("SOULKU"), \
            ctx.get_messages()[0]["content"][:100]

        # 11. #4 edit pesan commit: confirm "edit:X" → commit pakai X
        import subprocess as _sp
        import tempfile as _tf
        from pathlib import Path as _Path
        tmp = _Path(_tf.mkdtemp(prefix="multacd-commit-"))
        _sp.run(["git", "-C", str(tmp), "init", "-b", "main"],
                capture_output=True, timeout=30, check=True)
        _sp.run(["git", "-C", str(tmp), "config", "user.email", "t@t"],
                capture_output=True, timeout=30, check=True)
        _sp.run(["git", "-C", str(tmp), "config", "user.name", "t"],
                capture_output=True, timeout=30, check=True)
        (tmp / "a.txt").write_text("x")
        _sp.run(["git", "-C", str(tmp), "add", "."],
                capture_output=True, timeout=30, check=True)

        async def _edit(name, params):
            assert name == "git_commit", name
            return "edit:pesan edit e2e"
        fake5 = FakeLLM([StreamDone("", [_TCR(
            "c1", "git_commit",
            {"workdir": str(tmp), "message": "pesan awal"})]),
            StreamDone("done", [])])
        ctx = ConversationContext()
        events = await _drain(run_agent("commit", ctx, cfg, llm_client=fake5,
                                        confirm=_edit))
        assert any(isinstance(e, AgentToolDone) and e.success for e in events)
        log = _sp.run(["git", "-C", str(tmp), "log", "--format=%s"],
                      capture_output=True, text=True, timeout=30)
        assert "pesan edit e2e" in log.stdout, log.stdout

        # 12. #4 branch baru: push main ditolak → "branch" → buat + push ulang
        async def _branch(name, params):
            assert name == "git_push", name
            return "branch"
        fake6 = FakeLLM([StreamDone("", [_TCR(
            "c1", "git_push", {"workdir": str(tmp)})]),
            StreamDone("done", [])])
        ctx = ConversationContext()
        events = await _drain(run_agent(
            "push", ctx, cfg, llm_client=fake6, confirm=_branch,
            ask_user=lambda q: _asyncio.sleep(0, result="fitur-e2e")))
        br = _sp.run(["git", "-C", str(tmp), "branch", "--list"],
                     capture_output=True, text=True, timeout=30)
        assert "fitur-e2e" in br.stdout, br.stdout
        push_done = [e for e in events if isinstance(e, AgentToolDone)]
        assert push_done and "fitur-e2e" in str(
            ctx.get_messages()), "push harus diarahkan ke branch baru"

        print("✅ agent_loop self-test OK (12 skenario)")

    async def _no_confirm(name, params):
        raise AssertionError(f"tidak boleh minta konfirmasi untuk {name}")

    _asyncio.run(main())
