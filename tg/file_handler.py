"""File handling Telegram — terima & kirim file (PLAN Phase 4 Step 5).

Terima: dokumen/foto → ~/.multacd/uploads/ → agent baca via read_file.
Kirim: agent panggil tool send_telegram(path) atau send_file_to() langsung.
Batas Telegram 50MB — lebih dari itu ditolak dengan pesan jelas.

Test cepat:
    python -m tg.file_handler
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

MAX_SEND_BYTES = 50 * 1024 * 1024  # batas Bot API

# Bisa dibaca agent sebagai teks langsung.
TEXT_SUFFIXES = frozenset({
    ".txt", ".md", ".markdown", ".py", ".js", ".ts", ".tsx", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv", ".log", ".html",
    ".css", ".go", ".rs", ".java", ".c", ".h", ".sh", ".sql",
})

# Disimpan + dicatat, tapi model teks tidak bisa "melihat".
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


def upload_dir() -> Path:
    """~/.multacd/uploads/ (hormati MULTACD_HOME buat isolasi test)."""
    d = Path(os.environ.get("MULTACD_HOME", str(Path.home()))) / ".multacd" / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sanitize_filename(name: str) -> str:
    """Basename aman: tanpa path traversal, maks 80 char."""
    base = Path(name or "file").name.strip() or "file"
    base = re.sub(r"[^A-Za-z0-9._\- ]", "_", base)
    return base[-80:] if len(base) > 80 else base


def save_bytes(data: bytes, filename: str) -> Path:
    """Simpan bytes ke uploads/ (dedupe otomatis). Return path lokal."""
    safe = sanitize_filename(filename)
    dest = upload_dir() / safe
    n = 1
    while dest.exists():
        dest = upload_dir() / f"{dest.stem}-{n}{dest.suffix}"
        n += 1
    dest.write_bytes(data)
    return dest


def _size_str(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def describe_for_agent(path: Path) -> str:
    """Pesan konteks buat agent saat user kirim file."""
    suffix = path.suffix.lower()
    size = _size_str(path.stat().st_size) if path.is_file() else "?"
    head = (f"User mengirim file: {path.name} ({suffix or 'tanpa ext'}, "
            f"{size}). Tersimpan di: {path}")
    if suffix in TEXT_SUFFIXES:
        return head + " Baca dengan read_file tool sesuai konteks."
    if suffix in IMAGE_SUFFIXES:
        return (head + " Ini gambar — model teks tidak bisa melihat isinya. "
                "Beri tahu user secara jujur, jangan mengarang.")
    if suffix == ".pdf":
        return head + " Coba baca sebagai teks; kalau gagal, beri tahu user."
    return head + " Kalau bisa dibaca sebagai teks, proses sesuai konteks."


async def download_from_telegram(file_id: str, filename: str,
                                 bot: Any) -> Path:
    """Download file Telegram ke uploads/. Butuh bot PTB asli."""
    tg_file = await bot.get_file(file_id)
    dest = upload_dir() / sanitize_filename(filename)
    n = 1
    while dest.exists():
        dest = upload_dir() / f"{dest.stem}-{n}{dest.suffix}"
        n += 1
    await tg_file.download_to_drive(str(dest))
    return dest


async def send_file_to(chat_id: int, path: Path, bot: Any,
                       caption: str = "") -> str | None:
    """Kirim file ke chat. Return pesan warning (dikirim sebagai teks)
    kalau > 50MB; None kalau terkirim."""
    size = path.stat().st_size
    if size > MAX_SEND_BYTES:
        return (f"File {path.name} ({_size_str(size)}) melebihi batas "
                "Telegram 50MB — tidak bisa dikirim.")
    with open(path, "rb") as fh:
        await bot.send_document(chat_id=chat_id, document=fh,
                                filename=path.name,
                                caption=caption[:1024] or None)
    return None


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as home:
        os.environ["MULTACD_HOME"] = home
        p = save_bytes(b"hello", "report.pdf")
        assert p.is_file() and p.parent.name == "uploads"
        p2 = save_bytes(b"hello", "report.pdf")
        assert p2.name == "report-1.pdf"  # dedupe
        assert sanitize_filename("../../etc/passwd") == "passwd"
        assert sanitize_filename("") == "file"

        desc = describe_for_agent(p)
        assert "report.pdf" in desc and str(p) in desc
        txt = save_bytes(b"x = 1", "a.py")
        assert "read_file" in describe_for_agent(txt)
        img = save_bytes(b"\x89PNG", "foto.png")
        assert "tidak bisa melihat" in describe_for_agent(img)

        big = save_bytes(b"x", "big.bin")

        class _Bot:
            async def send_document(self, **kwargs: Any) -> None:
                raise AssertionError("tidak boleh dipanggil")

        async def _go() -> None:
            # Fake ukuran > 50MB via monkeypatch stat? pakai file kecil:
            # kirim sukses dengan bot fake.
            sent: list = []

            class _Bot2:
                async def send_document(self, chat_id: int, document: Any,
                                        filename: str,
                                        caption: Any) -> None:
                    sent.append((chat_id, filename))

            assert await send_file_to(1, txt, _Bot2()) is None
            assert sent == [(1, "a.py")]

        import asyncio as _asyncio
        _asyncio.run(_go())
        del os.environ["MULTACD_HOME"]

    print("✅ file_handler self-test OK (save + describe + send)")
