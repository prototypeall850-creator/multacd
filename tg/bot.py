"""Telegram bot — init Application + register handler (PLAN Phase 4 §7).

Token kosong → ValueError jelas (isi via wizard/manual dulu).
run_polling() blocking — dipakai daemon mode (Step 8).

Test cepat:
    python -m tg.bot
"""

from __future__ import annotations

from typing import Any

from core.config import Config
from tg.access_control import AccessControl
from tg.handlers import on_message


class MultacdBot:
    """Wrapper tipis PTB Application. Agent loop masuk Step 4."""

    def __init__(self, config: Config,
                 access_control: AccessControl | None = None) -> None:
        token = (config.telegram.bot_token or "").strip()
        if not token:
            raise ValueError(
                "telegram.bot_token kosong — isi via setup wizard "
                "atau manual di config.yaml.")
        try:
            from telegram.ext import Application, MessageHandler, filters
        except ImportError as e:
            raise ValueError(
                "python-telegram-bot belum terinstall: "
                "./.venv/bin/python -m pip install python-telegram-bot>=21.0"
            ) from e
        self.config = config
        self.ac = access_control or AccessControl(config)
        self.app = Application.builder().token(token).build()
        self.app.bot_data["ac"] = self.ac
        self.app.bot_data["admin_username"] = config.telegram.admin_username
        self.app.bot_data["admin_id"] = config.telegram.admin_id
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                            on_message))
        # Command juga lewat route_message (support /userbaru@namabot).
        self.app.add_handler(MessageHandler(filters.COMMAND, on_message))
        self.app.add_error_handler(self.on_error)

    @staticmethod
    async def on_error(update: Any, context: Any) -> None:
        """Log error PTB tanpa matikan polling."""
        print(f"⚠️ telegram error: {context.error}")

    def run_polling(self) -> None:
        """Blocking — jalan sampai Ctrl+C (dipakai daemon)."""
        print("🤖 bot polling mulai (Ctrl+C berhenti)...")
        self.app.run_polling()


if __name__ == "__main__":
    from core.config import Config as _Config

    # 1. Token kosong → error jelas.
    try:
        MultacdBot(_Config(model="m", api_key="k"))
        raise AssertionError("harus ValueError")
    except ValueError as e:
        assert "bot_token" in str(e)

    # 2. Token dummy → app kebangun, handler terdaftar (tanpa network).
    _cfg = _Config(model="m", api_key="k", telegram={
        "bot_token": "123:ABC", "admin_id": 1, "admin_username": "u"})
    _bot = MultacdBot(_cfg)
    assert len(_bot.app.handlers.get(0, [])) == 2, "text + command handler"
    assert _bot.app.bot_data["admin_id"] == 1

    print("✅ bot self-test OK (guard + build + handlers)")
