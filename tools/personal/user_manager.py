"""user_manager — kelola whitelist Telegram dari TUI /personal. ASK-REQUIRED.

Setara /userbaru Telegram tapi lewat agent. Tulis ke config.yaml nyata
(active config atau default path) — makanya selalu konfirmasi dulu.

Test cepat:
    python -m tools.personal.user_manager
"""

from __future__ import annotations

from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "user_manager",
        "description": ("Kelola user bot Telegram: list (lihat), "
                        "add (beri akses), remove (cabut akses)."),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string",
                           "description": "list | add | remove"},
                "user_id": {"type": "integer", "default": 0,
                            "description": "ID Telegram (wajib utk add/remove)"},
            },
            "required": ["action"],
        },
    },
}


def user_manager(action: str, user_id: int = 0) -> dict[str, Any]:
    from core.config import get_active_config, load_config, resolve_config_path
    from tg.access_control import AccessControl

    action = (action or "").strip().lower()
    if action not in ("list", "add", "remove"):
        return fail("action harus list | add | remove.")
    try:
        cfg = get_active_config() or load_config()
    except SystemExit:
        return fail("Config belum ada — setup dulu.")
    ac = AccessControl(cfg)
    if action == "list":
        users = ac.get_users()
        if not users:
            return ok("(belum ada user terdaftar)")
        return ok("User aktif:\n" + "\n".join(f"- {u}" for u in users))
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return fail(f"user_id harus angka: {user_id}")
    if action == "add":
        if not ac.add_user(uid):
            return fail(f"User {uid} sudah terdaftar / tidak valid.")
        ac.save_to(resolve_config_path())
        return ok(f"User {uid} ditambahkan. Bot kirim welcome saat ia /start.")
    if not ac.remove_user(uid):
        return fail(f"User {uid} tidak terdaftar.")
    ac.save_to(resolve_config_path())
    return ok(f"User {uid} dihapus.")


if __name__ == "__main__":
    # MULTACD_HOME WAJIB di-set sebelum import core.config
    # (DEFAULT_CONFIG_PATH di-freeze saat import).
    import os
    import tempfile
    _home = tempfile.TemporaryDirectory()
    os.environ["MULTACD_HOME"] = _home.name

    from pathlib import Path

    import yaml

    from core.config import set_active_config as _set

    try:
        cfg_path = Path(_home.name) / ".multacd" / "config.yaml"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(yaml.safe_dump({
            "model": "m", "api_key": "k",
            "telegram": {"admin_id": 1, "allowed_users": []}}),
            encoding="utf-8")
        assert user_manager("list")["result"] == "(belum ada user terdaftar)"
        assert user_manager("add", 7)["success"]
        assert "tidak valid" in user_manager("add", 1)["error"]  # admin
        assert user_manager("list")["result"] == "User aktif:\n- 7"
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert raw["telegram"]["allowed_users"] == [7]  # persist nyata
        assert user_manager("remove", 7)["success"]
        assert not user_manager("remove", 7)["success"]
        assert not user_manager("ngawur")["success"]
    finally:
        del os.environ["MULTACD_HOME"]
        _home.cleanup()
    _set(None)

    print("✅ user_manager self-test OK (list/add/remove+persist)")
