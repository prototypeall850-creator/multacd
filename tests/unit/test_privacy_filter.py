"""Unit: privacy filter — tag, auto-detect, no-leak."""

from __future__ import annotations

from briefing.privacy import PrivacyFilter


def test_explicit_tags_private():
    f = PrivacyFilter()
    for tag in ("[private] x", "[PRIVATE] y", "# private: z", ">>private: w"):
        clean, priv = f.filter(tag)
        assert clean.strip() == "" and len(priv) == 1, tag


def test_plain_text_passes():
    f = PrivacyFilter()
    assert not f.is_sensitive_line("Beli susu besok")
    assert f.filter("") == ("", [])


def test_auto_detect_password_and_key():
    f = PrivacyFilter()
    assert f.is_sensitive_line("db password: hunter2")
    assert f.is_sensitive_line("api_key=tvly-abc123XYZ")


def test_mixed_no_leak():
    f = PrivacyFilter()
    mixed = "\n".join([
        "- Beli susu besok",
        "[private] Password database: xxxxx",
        "- Meeting klien jam 3",
        "api_key = sk-1234567890abcdefghij",
    ])
    clean, priv = f.filter(mixed)
    assert "Beli susu" in clean and "Meeting" in clean
    assert "xxxxx" not in clean and "sk-1234" not in clean
    assert len(priv) == 2
