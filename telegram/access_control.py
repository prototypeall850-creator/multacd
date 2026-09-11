"""Access control — admin / user / stranger (PLAN Phase 4 §6).

Aturan:
    admin    → user_id == telegram.admin_id
    user     → user_id di telegram.allowed_users
    stranger → sisanya (auto-reply + ignore setelah pesan pertama)

add/remove_update config model in-memory; save_to(path) patch yaml di disk
(tanpa menghapus key lain/komentar struktur — baca, update, tulis ulang).

Test cepat:
    python -m telegram.access_control
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml

from core.config import Config

Role = Literal["admin", "user", "stranger"]


class AccessControl:
    """Resolver whitelist. Pegang referensi Config agar TUI/bot konsisten."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self.admin_id = config.telegram.admin_id or 0
        self._users: set[int] = set(config.telegram.allowed_users or [])

    def check(self, user_id: int) -> Role:
        """Klasifikasikan pengirim pesan Telegram."""
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return "stranger"
        if self.admin_id and uid == self.admin_id:
            return "admin"
        if uid in self._users:
            return "user"
        return "stranger"

    def add_user(self, user_id: int) -> bool:
        """Tambah ke whitelist. False kalau admin/sudah ada/tidak valid."""
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return False
        if uid <= 0 or uid == self.admin_id or uid in self._users:
            return False
        self._users.add(uid)
        self._config.telegram.allowed_users = sorted(self._users)
        return True

    def remove_user(self, user_id: int) -> bool:
        """Hapus dari whitelist. False kalau tidak terdaftar."""
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return False
        if uid not in self._users:
            return False
        self._users.discard(uid)
        self._config.telegram.allowed_users = sorted(self._users)
        return True

    def get_users(self) -> list[int]:
        """Daftar user aktif terurut."""
        return sorted(self._users)

    def save_to(self, path: Path | str) -> None:
        """Patch allowed_users di config.yaml (key lain dipertahankan)."""
        p = Path(path).expanduser()
        try:
            raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except OSError:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        tg = raw.get("telegram")
        if not isinstance(tg, dict):
            tg = {}
        tg["allowed_users"] = sorted(self._users)
        # Pertahankan kredensial dari model kalau yaml belum punya.
        tg.setdefault("bot_token", self._config.telegram.bot_token)
        tg.setdefault("admin_id", self._config.telegram.admin_id)
        tg.setdefault("admin_username",
                      self._config.telegram.admin_username)
        raw["telegram"] = tg
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            yaml.safe_dump(dict(raw), fh, sort_keys=False,
                           allow_unicode=True)


if __name__ == "__main__":
    import tempfile

    cfg = Config(model="m", api_key="k", telegram={
        "bot_token": "t", "admin_id": 1, "admin_username": "u",
        "allowed_users": [2]})
    ac = AccessControl(cfg)
    assert ac.check(1) == "admin"
    assert ac.check(2) == "user"
    assert ac.check(999) == "stranger"
    assert ac.check("ngawur") == "stranger"

    assert ac.add_user(3) and ac.check(3) == "user"
    assert cfg.telegram.allowed_users == [2, 3]  # model ikut update
    assert not ac.add_user(3) and not ac.add_user(1)  # duplikat/admin
    assert not ac.add_user(0) and not ac.add_user("x")
    assert ac.remove_user(2) and ac.check(2) == "stranger"
    assert not ac.remove_user(2)
    assert ac.get_users() == [3]

    # save_to patch yaml tanpa hapus key lain.
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "config.yaml"
        p.write_text("model: m\napi_key: k\nother: 1\n",
                     encoding="utf-8")
        ac.save_to(p)
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert raw["other"] == 1
        assert raw["telegram"]["allowed_users"] == [3]
        assert raw["telegram"]["admin_id"] == 1

    print("✅ access_control self-test OK (roles + whitelist + save)")
