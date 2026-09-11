"""send_telegram — kirim pesan/file ke Telegram via Bot API. PERSONAL.

Target "admin" = telegram.admin_id di config aktif (hormati --config).
Content = teks biasa ATAU path file lokal (otomatis jadi dokumen).
Tanpa config aktif → fallback load_config() (standalone/CLI).

Permission: teks AUTO, file ASK (eskalasi param-aware di PermissionChecker,
pola yang sama seperti lint_python fix=true).

Test cepat:
    python -m tools.personal.send_telegram
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "send_telegram",
        "description": ("Kirim pesan teks atau file ke Telegram. "
                        "target 'admin' = admin di config. "
                        "content teks → pesan, path file → dokumen."),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string",
                           "description": "'admin' atau chat_id angka"},
                "content": {"type": "string",
                            "description": "teks pesan atau path file lokal"},
                "caption": {"type": "string", "default": "",
                            "description": "caption dokumen (abaikan utk teks)"},
            },
            "required": ["content"],
        },
    },
}

MAX_SEND_BYTES = 50 * 1024 * 1024


def is_file_content(content: str) -> bool:
    """True kalau content merujuk ke file lokal (untuk eskalasi ASK)."""
    text = (content or "").strip()
    if not text or "\n" in text or len(text) > 500:
        return False
    return Path(text).expanduser().is_file()


def _api(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def send_telegram(content: str, target: str = "admin",
                  caption: str = "") -> dict[str, Any]:
    if not (content or "").strip():
        return fail("content tidak boleh kosong.")
    from core.config import get_active_config, load_config
    try:
        cfg = get_active_config() or load_config()
    except SystemExit:
        return fail("Telegram belum disetup (isi telegram.bot_token).")
    token = (cfg.telegram.bot_token or "").strip()
    if not token:
        return fail("telegram.bot_token kosong — setup via wizard dulu.")
    if str(target).strip().lower() == "admin":
        chat_id = cfg.telegram.admin_id
        if not chat_id:
            return fail("telegram.admin_id kosong.")
    else:
        try:
            chat_id = int(str(target).strip())
        except ValueError:
            return fail(f"target harus 'admin' atau chat_id angka: {target}")
    try:
        if is_file_content(content):
            path = Path(content.strip()).expanduser()
            size = path.stat().st_size
            if size > MAX_SEND_BYTES:
                return fail(f"File > 50MB ({size} byte), Telegram menolak.")
            with open(path, "rb") as fh:
                resp = httpx.post(
                    _api(token, "sendDocument"), timeout=60,
                    data={"chat_id": chat_id,
                          "caption": (caption or "")[:1024]},
                    files={"document": (path.name, fh)})
        else:
            resp = httpx.post(
                _api(token, "sendMessage"), timeout=30,
                json={"chat_id": chat_id, "text": content[:4096]})
        resp.raise_for_status()
    except httpx.TimeoutException:
        return fail("Timeout hubungi Telegram.")
    except httpx.HTTPStatusError as e:
        return fail(f"Telegram HTTP {e.response.status_code} "
                    "(cek bot_token / user sudah /start ke bot?).")
    except httpx.HTTPError as e:
        return fail(f"Gagal kirim Telegram: {e}")
    except OSError as e:
        return fail(f"Gagal baca file: {e}")
    return ok(f"Terkirim ke {chat_id}.")


if __name__ == "__main__":
    import tempfile as _tf

    from core.config import Config as _Config
    from core.config import set_active_config as _set

    # 1. Heuristik file vs teks.
    assert not is_file_content("halo apa kabar")
    assert not is_file_content("")
    with _tf.NamedTemporaryFile(suffix=".md", delete=False) as fh:
        fh.write(b"# riset")
        _tmp = fh.name
    try:
        assert is_file_content(_tmp)
        assert not is_file_content(_tmp + " tambahan kata")
    finally:
        Path(_tmp).unlink(missing_ok=True)

    # 2. Tanpa token → fail jelas (tanpa network).
    _set(_Config(model="m", api_key="k"))
    try:
        r = send_telegram("halo")
        assert not r["success"] and "bot_token" in r["error"], r
    finally:
        _set(None)

    # 3. Mock httpx: teks → sendMessage, file → sendDocument.
    _calls: list = []

    class _Resp:
        def raise_for_status(self) -> None:
            pass

    def _fake_post(url: str, **kwargs: Any) -> _Resp:
        _calls.append((url, kwargs))
        return _Resp()

    _orig = httpx.post
    httpx.post = _fake_post  # type: ignore[method-assign]
    _set(_Config(model="m", api_key="k", telegram={
        "bot_token": "tok", "admin_id": 9}))
    try:
        r = send_telegram("halo admin")
        assert r["success"], r
        assert _calls[-1][0].endswith("/sendMessage")
        assert _calls[-1][1]["json"]["chat_id"] == 9
        with _tf.NamedTemporaryFile(suffix=".md", delete=False) as fh:
            fh.write(b"x")
            _f2 = fh.name
        try:
            r = send_telegram(_f2, caption="hasil")
            assert r["success"], r
            assert _calls[-1][0].endswith("/sendDocument")
        finally:
            Path(_f2).unlink(missing_ok=True)
        r = send_telegram("x", target="bukanangka")
        assert not r["success"] and "chat_id" in r["error"]
    finally:
        httpx.post = _orig
        _set(None)

    print("✅ send_telegram self-test OK (heuristik + guard + mock)")
