"""Model selector popup — searchable, grouped per provider (DESIGN §12 v2).

Buka: ketik `/model` tanpa argumen (MainScreen intersep) atau Ctrl+O.
Pilih → submit `/model <nama>` seperti ketik manual. Esc tutup.

Fitur v2 (full bebas, Termux-first):
- Filter fuzzy berperingkat (sama kayak slash palette).
- Recent (sesi ini) + Favorites (persist ~/.multacd/favorites.json).
- Tag Free (provider gratis) / Local (ollama). ctrl+f favorite.
- Grouping per provider; sempit (<70 kolom) → 1 baris per item ringkas.
"""

from __future__ import annotations

import json
import os
from contextlib import suppress
from pathlib import Path

from textual.containers import Vertical
from textual.widgets import Label, ListItem, ListView, Static

# Katalog kurasi (provider → [(model, tag)]). Tag: "" | "Free" | "Local".
# Bukan fetch live — selector harus instan walau offline; model baru
# tetap bisa diketik manual `/model <nama>`.
CATALOG: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("Anthropic", (
        ("claude-sonnet-4-6", ""),
        ("claude-opus-4", ""),
        ("claude-haiku-4-5", ""),
    )),
    ("OpenAI", (
        ("gpt-4o", ""),
        ("gpt-4o-mini", ""),
        ("o3", ""),
    )),
    ("Google", (
        ("gemini-2.0-flash", ""),
        ("gemini-2.5-pro", ""),
    )),
    ("Groq", (
        ("llama-3.3-70b-versatile", "Free"),
        ("llama-3.1-8b-instant", "Free"),
    )),
    ("Ollama (local)", (
        ("llama3.2", "Local"),
        ("qwen2.5-coder", "Local"),
    )),
)

# Provider katalog → prefix config model (filter sesuai yang dikonfigurasi).
PROVIDER_PREFIX = {
    "Anthropic": ("anthropic/", "claude-"),
    "OpenAI": ("openai/", "gpt-", "o3", "o1"),
    "Google": ("gemini/",),
    "Groq": ("groq/",),
    "Ollama (local)": ("ollama/",),
}


def _favorites_path() -> Path:
    base = Path(os.environ.get("MULTACD_HOME", str(Path.home())))
    return base / ".multacd" / "favorites.json"


def load_favorites() -> list[str]:
    """Favorit persist. Gagal baca → [] (tidak pernah raise)."""
    try:
        raw = json.loads(_favorites_path().read_text(encoding="utf-8"))
        return [str(x) for x in raw] if isinstance(raw, list) else []
    except Exception:
        return []


def save_favorites(names: list[str]) -> None:
    """Simpan favorit. Gagal tulis → silent (bukan blocker sesi)."""
    try:
        p = _favorites_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(sorted(set(names)), indent=1), encoding="utf-8")
    except Exception:
        pass


def all_models() -> list[tuple[str, str, str]]:
    """Flatten katalog → [(provider, model, tag)]."""
    out = []
    for provider, models in CATALOG:
        for name, tag in models:
            out.append((provider, name, tag))
    return out


def for_configured(config_model: str) -> list[tuple[str, str, str]]:
    """Filter katalog ke provider yang sedang dikonfigurasi + ollama (lokal).

    Model aktif selalu ikut (walau tak ada di katalog) biar tak hilang.
    """
    cur = (config_model or "").strip()
    low = cur.lower()
    if "/" in low:
        prov, name = low.split("/", 1)
    else:
        prov, name = "", low
    want: set[str] = set()
    for key, prefixes in PROVIDER_PREFIX.items():
        if any(low.startswith(p) or p.rstrip("/") == prov for p in prefixes):
            want.add(key)
    pool = all_models()
    # Tak dikenali → tampil semua (jangan kosong).
    keep = [m for m in pool
            if not want or m[0] in want or m[0] == "Ollama (local)"]
    if cur and all(m[1] != cur and m[1] != name for m in keep):
        keep.insert(0, ("Current", cur, ""))
    return keep


def match_models(query: str,
                 models: list[tuple[str, str, str]] | None = None,
                 ) -> list[tuple[str, str, str]]:
    """Filter fuzzy berperingkat. '' → semua (recent/fav diurutkan caller)."""
    pool = models if models is not None else all_models()
    needle = query.strip().lower()
    if not needle:
        return list(pool)
    scored = []
    for provider, name, tag in pool:
        n = name.lower()
        if n.startswith(needle):
            scored.append((0, provider, name, tag))
        elif needle in n:
            scored.append((1, provider, name, tag))
        else:
            it = iter(n)
            if all(ch in it for ch in needle):
                scored.append((2, provider, name, tag))
    scored.sort(key=lambda x: (x[0], x[2]))
    return [(p, n, t) for _, p, n, t in scored]


class ModelSelector(Vertical):
    """Popup pilih model. State di sini, aksi via screen."""

    def __init__(self) -> None:
        super().__init__(id="model-selector")
        self._pool: list[tuple[str, str, str]] = []
        self._matches: list[tuple[str, str, str]] = []
        self._index = 0
        self._query = ""
        self._recent: list[str] = []
        self._favorites: list[str] = load_favorites()

    def compose(self):
        yield Static("Select model   esc", id="model-title")
        yield Static("", id="model-query")
        yield ListView(id="model-list")

    @property
    def is_open(self) -> bool:
        return self.display

    @property
    def selected(self) -> str | None:
        if not self._matches:
            return None
        return self._matches[self._index][1]

    def open(self, config_model: str = "") -> None:
        self._pool = for_configured(config_model)
        # Urut: favorit → recent → sisanya (dalam pool order).
        fav = [m for m in self._pool if m[1] in self._favorites]
        rec = [m for m in self._pool
               if m[1] in self._recent and m[1] not in self._favorites]
        rest = [m for m in self._pool
                if m[1] not in self._favorites and m[1] not in self._recent]
        self._pool = fav + rec + rest
        self._query = ""
        self._matches = list(self._pool)
        self._index = 0
        self._rebuild()
        self.display = True

    def refilter(self, query: str) -> None:
        if not self.display:
            return
        self._query = query
        self._matches = match_models(query, self._pool)
        self._index = 0
        self._rebuild()

    def close(self) -> None:
        self.display = False
        self._matches = []
        self._index = 0

    def move(self, delta: int) -> None:
        if not self._matches:
            return
        self._index = (self._index + delta) % len(self._matches)
        self._highlight()

    def toggle_favorite(self) -> str | None:
        """ctrl+f: favoritkan/batalkan yang disorot. Return nama bila ada."""
        name = self.selected
        if name is None:
            return None
        if name in self._favorites:
            self._favorites.remove(name)
        else:
            self._favorites.append(name)
        save_favorites(self._favorites)
        self._rebuild()
        return name

    def mark_used(self, name: str) -> None:
        """Catat model terpilih ke recent (max 5)."""
        if name in self._recent:
            self._recent.remove(name)
        self._recent.insert(0, name)
        self._recent = self._recent[:5]

    def _rebuild(self) -> None:
        try:
            lst = self.query_one("#model-list", ListView)
        except Exception:
            return
        with suppress(Exception):
            self.query_one("#model-query", Static).update(
                f"Search: {self._query or '...'}  (ctrl+f favorite)")
        lst.clear()
        for provider, name, tag in self._matches:
            star = "*" if name in self._favorites else " "
            tag_s = f"  [{tag}]" if tag else ""
            lst.append(ListItem(Label(f"{star} {name}  ({provider}){tag_s}")))
        self._highlight()

    def _highlight(self) -> None:
        try:
            lst = self.query_one("#model-list", ListView)
            if self._matches:
                lst.index = self._index
        except Exception:
            pass


if __name__ == "__main__":
    assert len(all_models()) == 12
    assert [m for _, m, _ in match_models("qwen")] == ["qwen2.5-coder"]
    got_gmn = [m for _, m, _ in match_models("gmn")]  # fuzzy subsequence
    assert "gemini-2.0-flash" in got_gmn and "gemini-2.5-pro" in got_gmn
    got = [m for _, m, _ in match_models("llama")]
    assert "llama3.2" in got and "llama-3.3-70b-versatile" in got
    assert match_models("zzz") == []
    pool = for_configured("groq/llama-3.3-70b-versatile")
    assert any(m == "llama-3.3-70b-versatile" for _, m, _ in pool)
    assert any(p == "Ollama (local)" for p, _, _ in pool)  # lokal selalu ada
    assert load_favorites() == [] or isinstance(load_favorites(), list)
    print("✅ model_selector self-test OK (katalog + fuzzy)")
