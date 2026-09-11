"""Privacy filter — pisahkan item sensitif sebelum data dikirim ke LLM.

Kontrak (PLAN Phase 4 §5):
    filter(content) -> (clean_content, private_items)
    - Baris bertag [private] (semua format, case-insensitive) → private.
    - Baris auto-sensitif (password, api key, token panjang) → private.
    - clean_content aman dikirim ke LLM; private_items diproses lokal.

Test cepat:
    python -m briefing.privacy
"""

from __future__ import annotations

import re

# Tag eksplisit: [private], # private:, >>private: (case-insensitive).
PRIVATE_PATTERNS = [
    r"\[private\]",
    r"#\s*private\s*:",
    r">>\s*private\s*:",
]

# Auto-detect: pola password/secret/kunci + token panjang mirip API key.
AUTO_SENSITIVE_PATTERNS = [
    r"password[:\s=]",
    r"passwd[:\s=]",
    r"secret[:\s=]",
    r"api.?key[:\s=]",
    r"\b(?:sk|tvly|exa|brv|tavily)[-_][A-Za-z0-9_\-]{8,}",
    r"\b[A-Za-z0-9_\-]{20,}\b",
    r"\b\d{4}[-\s]?\d{4}[-\s]?\d{2,}\b",
]

_TAG_RE = re.compile("|".join(f"(?:{p})" for p in PRIVATE_PATTERNS),
                     re.IGNORECASE)
_AUTO_RES = [re.compile(p, re.IGNORECASE)
             for p in AUTO_SENSITIVE_PATTERNS]


def _clean_item(line: str) -> str:
    """Buang tag [private] + marker list, sisakan isi mentah."""
    item = _TAG_RE.sub("", line).strip()
    return re.sub(r"^[\-\*>\s]+", "", item).strip()


class PrivacyFilter:
    """Filter stateless — satu instance bisa dipakai ulang."""

    def is_sensitive_line(self, line: str) -> bool:
        """True kalau baris bertag private atau cocok pola sensitif."""
        if not line or not line.strip():
            return False
        if _TAG_RE.search(line):
            return True
        return any(r.search(line) for r in _AUTO_RES)

    def filter(self, content: str) -> tuple[str, list[str]]:
        """Pisahkan konten. Return (bersih_untuk_LLM, item_private)."""
        if not content:
            return "", []
        clean_lines: list[str] = []
        private_items: list[str] = []
        for line in content.splitlines():
            if self.is_sensitive_line(line):
                item = _clean_item(line)
                private_items.append(item or line.strip())
            else:
                clean_lines.append(line)
        return "\n".join(clean_lines), private_items


if __name__ == "__main__":
    f = PrivacyFilter()

    # 1. Semua format tag eksplisit (case-insensitive).
    for tag in ("[private] Password db: x", "[PRIVATE] No rek: 1",
                "- # private: antar obat", ">>private: token abc",
                ">>PRIVATE: rahasia", "# PRIVATE: pin"):
        assert f.is_sensitive_line(tag), tag
        clean, priv = f.filter(tag)
        assert clean.strip() == "" and len(priv) == 1, tag
        assert _TAG_RE.search(tag) and not _TAG_RE.search(priv[0]), tag

    # 2. Baris biasa lolos, kosong diabaikan.
    assert not f.is_sensitive_line("Beli susu besok")
    assert not f.is_sensitive_line("")
    assert not f.is_sensitive_line("   ")

    # 3. Auto-detect tanpa tag: password + key panjang.
    assert f.is_sensitive_line("db password: hunter2")
    assert f.is_sensitive_line("api_key=tvly-abc123XYZ")
    assert f.is_sensitive_line("token sk-ant-abcd1234efgh")
    assert f.is_sensitive_line("kartu 1234-5678-9012")

    # 4. Campuran: bersih tidak bocor, private lengkap.
    mixed = "\n".join([
        "- Beli susu besok",
        "[private] Password database: xxxxx",
        "- Meeting klien jam 3",
        "api_key = sk-1234567890abcdefghij",
    ])
    clean, priv = f.filter(mixed)
    assert "Beli susu" in clean and "Meeting" in clean
    assert "xxxxx" not in clean and "sk-1234" not in clean
    assert len(priv) == 2 and "Password database" in priv[0]

    # 5. Kosong & tanpa private.
    assert f.filter("") == ("", [])
    assert f.filter("a\nb") == ("a\nb", [])

    print("✅ privacy self-test OK (tag + auto-detect + no-leak)")
