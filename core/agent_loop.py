"""Agent loop — ReAct: Reason → Act → Observe.

Menyambungkan LLM + tools + memory + permission jadi satu loop.
Async generator — setiap update di-yield real-time ke TUI:

    async for event in run_agent(user_input, context, config):
        isinstance(event, AgentText)      → tampilkan potongan teks
        isinstance(event, AgentToolStart) → tampilkan 🔧 ... ⏳
        isinstance(event, AgentToolDone)  → update jadi ✅ / ❌
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
from typing import Any

from core.config import Config
from core.llm_client import LLMClient, LLMError, StreamDone, StreamText, setup_client
from core.permissions import PermissionChecker
from memory.context import ConversationContext
from tools.common import fail
from tools.registry import execute_tool, get_tool_definitions
from typing import TYPE_CHECKING

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


@dataclass
class AgentDone:
    text: str


@dataclass
class AgentError:
    message: str


AgentEvent = AgentText | AgentToolStart | AgentToolDone | AgentDone | AgentError


async def _stdin_confirm(tool_name: str, params: dict[str, Any]) -> str:
    target = params.get("path") or params.get("command") or params.get("url") or ""
    print(f"⚠️  {tool_name} {target} — izinkan? [y/n/a] ", end="", flush=True)
    try:
        ans = await asyncio.to_thread(input)
    except (EOFError, KeyboardInterrupt):
        return "no"
    ans = ans.strip().lower()
    if ans in ("a", "all"):
        return "all"
    return "yes" if ans in ("y", "yes") else "no"


async def _stdin_ask(question: str) -> str:
    print(f"❓ {question}")
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
    tools = defs if active_tools is None else [
        d for d in defs if d["function"]["name"] in set(active_tools)]

    if not context.get_messages():
        context.add_message("system", _system_prompt())
    context.add_message("user", user_input)

    iteration = 0
    while True:
        iteration += 1
        if iteration > config.max_tool_iterations:
            yield AgentError(
                f"⚠️ Mencapai batas {config.max_tool_iterations} iterasi tool. "
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
            assert done is not None
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
                context.add_tool_result(call.id, "ask",
                                        {"success": True, "result": answer, "error": None})
                yield AgentToolDone(call.id, "ask", True)
                continue

            decision = checker.check(call.name, call.arguments)
            if decision == "deny":
                context.add_tool_result(call.id, call.name, fail(
                    f"Tool `{call.name}` tidak tersedia. Pakai tool dari daftar yang ada."))
                yield AgentToolDone(call.id, call.name, False)
                continue

            if decision == "ask":
                choice = await confirm_cb(call.name, call.arguments)
                if choice == "all":
                    checker.approve_all_for_session(call.name)
                    choice = "yes"
                if choice != "yes":
                    context.add_tool_result(call.id, call.name, fail(
                        f"Dibatalkan user — jangan coba {call.name} yang sama lagi, "
                        "cari cara lain atau tanya user."))
                    yield AgentToolDone(call.id, call.name, False)
                    continue

            result = execute_tool(call.name, call.arguments)
            context.add_tool_result(call.id, call.name, result)
            yield AgentToolDone(call.id, call.name, result["success"])


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
        assert kinds == ["AgentText", "AgentText", "AgentToolStart", "AgentToolDone",
                         "AgentText", "AgentDone"], kinds
        assert events[3].success is True
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
        assert events[0].name == "write_file" and events[1].success is False
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
        assert events[1].success is False
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
        assert events[1].success is True
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

        print("✅ agent_loop self-test OK (10 skenario)")

    async def _no_confirm(name, params):
        raise AssertionError(f"tidak boleh minta konfirmasi untuk {name}")

    _asyncio.run(main())
