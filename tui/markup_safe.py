"""Escape teks dinamis biar aman di Static/Label markup (issue #29).

`textual.markup.escape` tidak cukup: regex-nya cuma `[a-z#/@]` sehingga
`[FOO=bar="x", y]` (key UPPERCASE) tetap crash MarkupError. Helper ini
escape SEMUA `[` (gandakan backslash yang sudah ada) — tanpa tergantung
quirks tokenizer Textual, jalan di semua versi textual.

Aturan pakai:
- teks polos tanpa niat markup → bungkus `rich.text.Text` (tanpa parse).
- template markup + lubang dinamis → `tx_escape(lubang)`.

Test cepat:
    python -m tui.markup_safe
"""

from __future__ import annotations

import re

_ESC_OPEN = re.compile(r"(\\*)\[")


def tx_escape(text: object) -> str:
    """Escape semua `[` jadi literal. No-op buat teks tanpa bracket."""
    def _rep(m: re.Match[str]) -> str:
        return m.group(1) * 2 + "\\["
    return _ESC_OPEN.sub(_rep, str(text))


if __name__ == "__main__":
    from textual.content import Content as _Content

    # No-op buat teks biasa (tak ada visual berubah).
    assert tx_escape("halo dunia") == "halo dunia"
    assert tx_escape("multacd v2.0.0b6") == "multacd v2.0.0b6"
    assert tx_escape(123) == "123"

    # Korpus ganas: SEMUA harus lolos from_markup setelah escape,
    # baik polos maupun di dalam template [dim]...[/].
    nasty = [
        '[foo=bar="list_dir", x]',   # repro persis #29
        '[FOO=bar="x", y]',          # escape() bawaan GAGAL di sini
        '["list_dir", "read_file"]',
        '{"name": "list_dir",}',
        "ls [a-z]* target[0]",
        "cmd[a=b, c] tail[",
        "Search: [",
        "[dim]grep foo[[/dim]",
        "a [b] c [B]hi",
        "back\\\\[slash [x=1]",
        "df[a==\"x\", b]",           # double ==
        "[a b=\"c\", d] [link=\"e\", f]",
        " feats: [x=y=\"a\", b] ok ",
    ]
    for s in nasty:
        _Content.from_markup(tx_escape(s))
        _Content.from_markup(f"[dim]{tx_escape(s)}[/dim]")
        _Content.from_markup(f"[bold]{tx_escape(s)}[/] {tx_escape(s)}")

    # Backslash yang sudah ada digandakan (render tetap apa adanya).
    assert tx_escape("[") == "\\["
    assert tx_escape("\\[") == "\\\\\\["
    _Content.from_markup(tx_escape("\\["))

    print("✅ markup_safe self-test OK (escape total + korpus #29)")
