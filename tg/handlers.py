"""Handler pesan Telegram — access check + admin command (PLAN Phase 4 §6-7).

Struktur dua lapis:
    route_message() — pure, tanpa I/O. Dipakai async handler DAN self-test.
    on_message()    — async PTB handler, I/O via update/context saja.

Step 3: user/admin dapat echo placeholder (+ /start, /help).
Step 4: pesan biasa → agent loop (tg.agent), pending Y/N via pesan berikut.

Test cepat:
    python -m tg.handlers
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tg.access_control import AccessControl

# Batas pesan Telegram (formatter Step 4 juga pakai ini).
TG_MAX_MESSAGE = 4096


def stranger_reply(admin_username: str) -> str:
    """Auto-reply pertama untuk stranger."""
    contact = f"@{admin_username}" if admin_username else "admin"
    return ("Akses tidak tersedia.\n"
            f"Hubungi admin {contact} untuk minta akses.")


def stranger_admin_notice(user_id: int, username: str, text: str) -> str:
    """Notifikasi ke admin saat stranger mencoba akses."""
    uname = f"@{username}" if username else "-"
    return ("! Percobaan akses:\n"
            f"   User ID: {user_id}\n"
            f"   Username: {uname}\n"
            f"   Pesan: {text[:200]}\n"
            f"   /userbaru {user_id} untuk beri akses.")


WELCOME = ("Halo! Saya multacd personal agent.\n"
           "Ketik /help untuk daftar perintah.")

HELP_USER = ("/start — pesan selamat datang\n"
             "/help — daftar perintah\n"
             "/clear — hapus history percakapan\n"
             "/briefing — minta briefing sekarang")

HELP_ADMIN = (HELP_USER + "\n"
              "/userbaru [id] — tambah user\n"
              "/hapususer [id] — hapus user\n"
              "/daftaruser — lihat user terdaftar\n"
              "/status — status daemon & scheduler")


def parse_admin_command(text: str) -> tuple[str, int | None] | None:
    """'/userbaru 123' → ('userbaru', 123). Bukan command → None."""
    parts = (text or "").strip().split()
    if not parts or not parts[0].startswith("/"):
        return None
    cmd = parts[0].lstrip("/").split("@")[0].lower()  # abaikan @namabot
    if cmd not in ("userbaru", "hapususer"):
        return None
    arg: int | None = None
    if len(parts) > 1:
        try:
            arg = int(parts[1])
        except ValueError:
            arg = None
    return cmd, arg


@dataclass
class RouteResult:
    """Hasil routing satu pesan: siapa + apa yang dikirim ke mana."""

    role: str                       # admin | user | stranger
    user_reply: str | None = None   # kirim ke pengirim
    admin_notice: str | None = None  # kirim ke admin (stranger flow)
    echo: bool = False              # user/admin biasa → echo placeholder


def route_message(user_id: int, username: str, text: str,
                  ac: AccessControl, admin_username: str) -> RouteResult:
    """Pure routing: tidak ada I/O, gampang di-test."""
    role = ac.check(user_id)
    if role == "stranger":
        return RouteResult(role, stranger_reply(admin_username),
                           stranger_admin_notice(user_id, username, text))
    if text.strip() == "/start":
        return RouteResult(role, WELCOME)
    if text.strip() == "/help":
        return RouteResult(
            role, HELP_ADMIN if role == "admin" else HELP_USER)
    if role == "admin":
        parsed = parse_admin_command(text)
        if parsed is not None:
            cmd, arg = parsed
            if arg is None:
                return RouteResult(role, f"ID tidak valid. Contoh: /{cmd} 987654321")
            if cmd == "userbaru":
                ok = ac.add_user(arg)
                return RouteResult(
                    role, f"User {arg} ditambahkan. Bot akan kirim welcome."
                    if ok else f"User {arg} sudah terdaftar / tidak valid.")
            ok = ac.remove_user(arg)
            return RouteResult(
                role, f"User {arg} dihapus."
                if ok else f"User {arg} tidak terdaftar.")
        if text.strip() == "/daftaruser":
            users = ac.get_users()
            body = "\n".join(f"- {u}" for u in users) or "- (kosong)"
            return RouteResult(role, f"Daftar user aktif ({len(users)}):\n{body}")
    return RouteResult(role, echo=True)


async def on_message(update: Any, context: Any) -> None:
    """Semua pesan → route. Stranger dibalas+notice; user/admin ke agent."""
    from tg.agent import resolve_pending, run_telegram_turn

    msg = update.effective_message or update.message
    user = update.effective_user
    bot_data = context.bot_data
    ac: AccessControl = bot_data["ac"]
    admin_username: str = bot_data.get("admin_username", "")
    admin_id: int = bot_data.get("admin_id", 0)
    text = msg.text or ""
    user_id = user.id

    if ac.check(user_id) == "stranger":
        await msg.reply_text(stranger_reply(admin_username)[:TG_MAX_MESSAGE])
        if admin_id:
            with _suppress():
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=stranger_admin_notice(
                        user_id, getattr(user, "username", "") or "",
                        text)[:TG_MAX_MESSAGE])
        return

    # Jawaban untuk pending confirm/ask dari turn yang jalan.
    pending = resolve_pending(bot_data, user_id, text)
    if pending == "handled":
        return
    busy = bot_data.setdefault("busy", set())
    if pending == "answered-new" and user_id in busy:
        await msg.reply_text("Bukan Y/N — tool ditolak. ⏳ Tunggu turn "
                             "selesai, lalu kirim ulang perintahmu.")
        return

    if user_id in busy:
        await msg.reply_text("⏳ Masih proses, tunggu sebentar ya.")
        return

    result = route_message(user_id, getattr(user, "username", "") or "",
                           text, ac, admin_username)
    if result.user_reply:
        await msg.reply_text(result.user_reply[:TG_MAX_MESSAGE])
        return
    if text.strip() == "/clear":
        bot_data.setdefault("contexts", {}).pop(user_id, None)
        await msg.reply_text("🧹 History dihapus. Mulai fresh!")
        return
    if text.strip() == "/briefing":
        await msg.reply_text("Briefing otomatis datang sesuai jadwal "
                             "(Step 7). Sabar ya ⏳")
        return

    busy.add(user_id)
    try:
        await run_telegram_turn(update, context, text)
    finally:
        busy.discard(user_id)
        # Sisa pending yatim (timeout race) jangan gantung selamanya.
        item = bot_data.get("pending", {}).pop(user_id, None)
        if item is not None and not item["future"].done():
            item["future"].cancel()


class _suppress:
    """Suppress pengiriman notif admin yang gagal (bot tetap jalan)."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: Any) -> bool:
        return True


if __name__ == "__main__":
    import asyncio as _asyncio

    from core.config import Config as _Config

    _cfg = _Config(model="m", api_key="k", telegram={
        "bot_token": "t", "admin_id": 1, "admin_username": "bos",
        "allowed_users": [2]})
    _ac = AccessControl(_cfg)

    # 1. Stranger: reply + notice.
    r = route_message(9, "aneh", "halo bang", _ac, "bos")
    assert r.role == "stranger" and "@bos" in (r.user_reply or "")
    assert "/userbaru 9" in (r.admin_notice or "")

    # 2. Admin command tambah/hapus/list.
    r = route_message(1, "bos", "/userbaru 7", _ac, "bos")
    assert "ditambahkan" in (r.user_reply or "") and _ac.check(7) == "user"
    assert "sudah terdaftar" in (route_message(
        1, "bos", "/userbaru 7", _ac, "bos").user_reply or "")
    assert "tidak valid" in (route_message(
        1, "bos", "/userbaru xx", _ac, "bos").user_reply or "")
    r = route_message(1, "bos", "/daftaruser", _ac, "bos")
    assert "7" in (r.user_reply or "")
    r = route_message(1, "bos", "/hapususer 7", _ac, "bos")
    assert "dihapus" in (r.user_reply or "") and _ac.check(7) == "stranger"
    assert "tidak terdaftar" in (route_message(
        1, "bos", "/hapususer 7", _ac, "bos").user_reply or "")

    # 3. /start /help beda admin vs user.
    assert "Halo" in (route_message(2, "u", "/start", _ac, "b").user_reply or "")
    assert "/userbaru" in (route_message(1, "b", "/help", _ac, "b").user_reply or "")
    assert "/userbaru" not in (route_message(2, "u", "/help", _ac, "b").user_reply or "")

    # 4. User biasa → echo placeholder.
    r = route_message(2, "u", "baca file x", _ac, "b")
    assert r.role == "user" and r.echo

    # 5. Async path pakai fake PTB (tanpa network).
    class _Msg:
        def __init__(self, text: str) -> None:
            self.text = text
            self.replies: list[str] = []

        async def reply_text(self, t: str) -> None:
            self.replies.append(t)

    class _User:
        def __init__(self) -> None:
            self.id = 9
            self.username = "aneh"

    class _Update:
        def __init__(self) -> None:
            self.effective_message = _Msg("halo")
            self.message = self.effective_message
            self.effective_user = _User()

    class _Bot:
        def __init__(self) -> None:
            self.sent: list[tuple[int, str]] = []

        async def send_message(self, chat_id: int, text: str) -> None:
            self.sent.append((chat_id, text))

    class _Ctx:
        def __init__(self) -> None:
            self.bot_data = {"ac": _ac, "admin_username": "bos",
                             "admin_id": 1}
            self.bot = _Bot()

    _upd, _ctx = _Update(), _Ctx()
    _asyncio.run(on_message(_upd, _ctx))
    assert any("Akses tidak tersedia" in r for r in _upd.message.replies)
    assert _ctx.bot.sent and _ctx.bot.sent[0][0] == 1

    # 6. User → agent turn (FakeLLM, tanpa provider).
    from core.llm_client import StreamDone as _SD
    from core.llm_client import StreamText as _ST

    class _FakeLLM:
        async def stream_completion(self, messages, tools=None):
            for word in ["Siap", "**bos**!"]:
                yield _ST(word + " ")
            yield _SD("Siap **bos**!", [])

    class _Bot2(_Bot):
        async def send_chat_action(self, chat_id: int, action: str) -> None:
            pass

    class _Chat:
        id = 2

    class _Update2(_Update):
        def __init__(self) -> None:
            self.effective_message = _Msg("halo bot")
            self.message = self.effective_message
            self.effective_user = _User()
            self.effective_user.id = 2
            self.effective_chat = _Chat()

    class _Ctx2:
        def __init__(self) -> None:
            self.bot_data = {"ac": _ac, "admin_username": "bos",
                             "admin_id": 1, "config": _cfg,
                             "llm": _FakeLLM()}
            self.bot = _Bot2()

    _upd2, _ctx2 = _Update2(), _Ctx2()
    _asyncio.run(on_message(_upd2, _ctx2))
    assert any("Siap bos!" in r for r in _upd2.message.replies), \
        _upd2.message.replies

    # 7. /clear hapus context user.
    _upd3, _ctx3 = _Update2(), _Ctx2()
    _ctx3.bot_data["contexts"] = {2: object()}
    _upd3.message.text = "/clear"
    _asyncio.run(on_message(_upd3, _ctx3))
    assert 2 not in _ctx3.bot_data["contexts"]
    assert any("History" in r for r in _upd3.message.replies)

    print("✅ handlers self-test OK (route + admin cmd + async fake)")
