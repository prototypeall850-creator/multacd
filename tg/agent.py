"""Agent turn via Telegram (PLAN Phase 4 Step 4).

Satu turn = satu task per user (busy guard). Konfirmasi tool & pertanyaan
agent dijawab lewat pesan berikutnya (pending future, timeout 60 dtk).
Tool berbahaya remote dimatikan via active_tools (tanpa ubah registry).

Test cepat:
    python -m tg.agent
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.agent_loop import AgentError, AgentText, run_agent
from core.llm_client import setup_client
from memory.context import ConversationContext
from tg.formatter import format_answer, format_tool_confirm
from tools.registry import TOOL_REGISTRY

# Tool yang TIDAK TERSEDIA di Telegram (terlalu berisiko remote).
TELEGRAM_DISABLED = frozenset({
    "run_python", "lint_python", "run_tests",       # eksekusi kode
    "multi_edit", "apply_patch", "move_file",       # tulis kompleks
    "delete_file",                                  # tidak bisa undo
    "git_push", "git_commit",                       # risiko remote
})

CONFIRM_TIMEOUT = 60  # detik — sesuai plan

_YES = {"y", "yes", "ya", "ok", "setuju"}
_NO = {"n", "no", "tidak", "nggak", "gak", "batal"}
_ALL = {"a", "all", "semua"}


def telegram_tools() -> list[str]:
    """Nama tool yang boleh dipakai agent via Telegram."""
    return [name for name in TOOL_REGISTRY if name not in TELEGRAM_DISABLED]


def get_context(bot_data: dict, user_id: int) -> ConversationContext:
    """Context per user (history terpisah), dibuat saat pertama chat."""
    contexts = bot_data.setdefault("contexts", {})
    ctx = contexts.get(user_id)
    if ctx is None:
        ctx = contexts[user_id] = ConversationContext()
    return ctx


def _pending(bot_data: dict) -> dict:
    return bot_data.setdefault("pending", {})


def _timeout(bot_data: dict) -> float:
    try:
        return float(bot_data.get("confirm_timeout", CONFIRM_TIMEOUT))
    except (TypeError, ValueError):
        return float(CONFIRM_TIMEOUT)


async def _wait_reply(bot_data: dict, user_id: int, kind: str,
                      prompt: str, send: Any) -> str:
    """Kirim prompt, tunggu pesan user berikutnya. Timeout → 'no'."""
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    _pending(bot_data)[user_id] = {"kind": kind, "future": fut}
    await send(prompt)
    try:
        return await asyncio.wait_for(fut, _timeout(bot_data))
    except (asyncio.TimeoutError, asyncio.CancelledError):
        await send("⏱️ Timeout 60 dtk — dibatalkan otomatis.")
        return "no"
    finally:
        _pending(bot_data).pop(user_id, None)


def resolve_pending(bot_data: dict, user_id: int, text: str) -> str | None:
    """Coba jawab pending user. Return 'handled' | 'answered-new' | None.

    - 'handled' → pesan adalah jawaban, turn lama lanjut. Stop di sini.
    - 'answered-new' → bukan jawaban: pending confirm di-"no"-kan, dan
      pesan boleh diproses sebagai turn baru (tapi busy guard yang putuskan).
    - None → tidak ada pending, proses normal.
    """
    item = _pending(bot_data).get(user_id)
    if item is None:
        return None
    fut = item["future"]
    if fut.done():
        return None
    word = (text or "").strip().lower()
    if item["kind"] == "ask":
        fut.set_result(text.strip() or "(kosong)")
        return "handled"
    if word in _YES:
        fut.set_result("yes")
        return "handled"
    if word in _NO:
        fut.set_result("no")
        return "handled"
    if word in _ALL:
        fut.set_result("all")
        return "handled"
    fut.set_result("no")  # bukan Y/N → tolak, pesan diproses baru
    return "answered-new"


async def _typing_loop(bot: Any, chat_id: int, stop: asyncio.Event) -> None:
    """Refresh typing indicator tiap 4 dtk selama turn jalan."""
    try:
        while not stop.is_set():
            with _ignore():
                await bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.wait_for(stop.wait(), 4)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass


class _ignore:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: Any) -> bool:
        return True


async def run_telegram_turn(update: Any, context: Any, text: str) -> None:
    """Jalankan satu turn agent, kirim jawaban final ke chat."""
    msg = update.effective_message or update.message
    user_id = update.effective_user.id
    chat = getattr(update, "effective_chat", None)
    chat_id = chat.id if chat is not None else user_id
    bot_data = context.bot_data
    config = bot_data["config"]
    if bot_data.get("llm") is None:
        bot_data["llm"] = setup_client(config)
    ctx = get_context(bot_data, user_id)

    async def _confirm(tool_name: str, params: dict[str, Any]) -> str:
        return await _wait_reply(
            bot_data, user_id, "confirm",
            format_tool_confirm(tool_name, params), msg.reply_text)

    async def _ask(question: str) -> str:
        ans = await _wait_reply(bot_data, user_id, "ask",
                                f"❓ {question}\nBalas dengan jawabanmu.",
                                msg.reply_text)
        return "(dibatalkan)" if ans == "no" else ans

    stop = asyncio.Event()
    typer = asyncio.create_task(_typing_loop(context.bot, chat_id, stop))
    try:
        collected: list[str] = []
        async for event in run_agent(
                text, ctx, config, llm_client=bot_data["llm"],
                confirm=_confirm, ask_user=_ask,
                active_tools=telegram_tools()):
            if isinstance(event, AgentText):
                collected.append(event.delta)
            elif isinstance(event, AgentError):
                collected.append(f"\n⚠️ {event.message}")
    finally:
        stop.set()
        typer.cancel()
    for part in format_answer("".join(collected).strip()):
        await msg.reply_text(part)


if __name__ == "__main__":
    from core.config import Config as _Config
    from core.llm_client import StreamDone, StreamText

    # 1. Subset tool: 44 - 9 disabled = 35.
    tools = telegram_tools()
    assert len(tools) == len(TOOL_REGISTRY) - len(TELEGRAM_DISABLED)
    assert "read_file" in tools and "delete_file" not in tools
    assert "run_python" not in tools and "quick_research" in tools

    # 2. Context per user terpisah.
    _bd: dict = {}
    assert get_context(_bd, 1) is get_context(_bd, 1)
    assert get_context(_bd, 1) is not get_context(_bd, 2)

    # 3. resolve_pending: y/n/bebas + ask free-text.
    async def _scenario() -> None:
        bd: dict = {}
        loop = asyncio.get_running_loop()

        async def _asker(kind: str) -> str:
            fut = loop.create_future()
            _pending(bd)[5] = {"kind": kind, "future": fut}
            return await fut

        t = asyncio.create_task(_asker("confirm"))
        await asyncio.sleep(0)
        assert resolve_pending(bd, 5, "Y") == "handled"
        assert await t == "yes"

        t = asyncio.create_task(_asker("confirm"))
        await asyncio.sleep(0)
        assert resolve_pending(bd, 5, "apa ini?") == "answered-new"
        assert await t == "no"

        t = asyncio.create_task(_asker("ask"))
        await asyncio.sleep(0)
        assert resolve_pending(bd, 5, "Bandung") == "handled"
        assert await t == "Bandung"

        assert resolve_pending(bd, 99, "y") is None

    asyncio.run(_scenario())

    # 4. Turn penuh pakai FakeLLM (tanpa network/provider).
    class _FakeLLM:
        def __init__(self, script: list) -> None:
            self.script = list(script)

        async def stream_completion(self, messages, tools=None):
            done = self.script.pop(0)
            for word in done.text.split():
                yield StreamText(word + " ")
                await asyncio.sleep(0)
            yield done

    class _Msg:
        def __init__(self, text: str = "halo") -> None:
            self.text = text
            self.replies: list[str] = []

        async def reply_text(self, t: str) -> None:
            self.replies.append(t)

    class _User:
        id = 7

    class _Chat:
        id = 7

    class _Update:
        def __init__(self) -> None:
            self.effective_message = _Msg()
            self.message = self.effective_message
            self.effective_user = _User()
            self.effective_chat = _Chat()

    class _Bot:
        async def send_chat_action(self, chat_id: int, action: str) -> None:
            pass

        async def send_message(self, chat_id: int, text: str) -> None:
            pass

    class _Ctx:
        def __init__(self, llm: Any) -> None:
            self.bot_data = {"config": _Config(model="m", api_key="k"),
                             "llm": llm, "confirm_timeout": 5}
            self.bot = _Bot()

    _upd = _Update()
    _ctx = _Ctx(_FakeLLM([StreamDone("Halo **bos**!", [])]))
    asyncio.run(run_telegram_turn(_upd, _ctx, "halo"))
    assert any("Halo bos!" in r for r in _upd.message.replies), \
        _upd.message.replies

    print("✅ agent self-test OK (subset + pending + turn)")
