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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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


@dataclass
class AgentText:
    delta: str


@dataclass
class AgentToolStart:
    call_id: str
    name: str
    params: dict[str, Any]


@dataclass
class AgentToolDone:
    call_id: str
    name: str
    success: bool
    result: dict[str, Any] | None = None  # payload penuh (D4: expandable view)


@dataclass
class AgentDone:
    text: str


@dataclass
class AgentUsage:
    """Token resmi provider untuk satu panggilan LLM (0 = tak dilapor)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0  # estimasi lokal (tabel harga provider)


@dataclass
class AgentError:
    message: str


AgentEvent = AgentText | AgentToolStart | AgentToolDone | AgentDone | AgentUsage | AgentError


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
) -> AsyncIterator[AgentEvent]:
    """Jalankan satu turn agent. Yield AgentEvent secara real-time."""
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
    checker = PermissionChecker(config)
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
    context.add_message("user", user_input)

    iteration = 0
    while True:
        iteration += 1
        if iteration > config.max_tool_iterations:
            yield AgentError(
                f"Mencapai batas {config.max_tool_iterations} iterasi tool. "
                "Berhenti agar tidak infinite loop — coba pecah tugas jadi langkah kecil."
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

        # ── Act + Observe: proses tiap tool call ──
        for call in done.tool_calls:
            yield AgentToolStart(call.id, call.name, call.arguments)

            # Tool "ask" dicegat: jawab via callback, bukan execute_tool (stdin).
            if call.name == "ask":
                question = call.arguments.get("question", "...")
                answer = await ask_cb(str(question))
                ask_result = {"success": True, "result": answer, "error": None}
                context.add_tool_result(call.id, "ask", ask_result)
                yield AgentToolDone(call.id, "ask", True, ask_result)
                continue

            decision = checker.check(call.name, call.arguments)
            if decision == "deny":
                deny_result = fail(
                    f"Tool `{call.name}` tidak tersedia. Pakai tool dari daftar yang ada.")
                context.add_tool_result(call.id, call.name, deny_result)
                yield AgentToolDone(call.id, call.name, False, deny_result)
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

        # 6. Infinite loop → berhenti di batas
        cfg2 = Config(model="m", api_key="k", max_tool_iterations=3)
        fake = FakeLLM([StreamDone("", [_TCR("c9", "list_dir", {})])] * 10)
        ctx = ConversationContext()
        events = await _drain(run_agent("loop", ctx, cfg2, llm_client=fake,
                                        confirm=_no_confirm))
        assert isinstance(events[-1], AgentError) and "3 iterasi" in events[-1].message

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
