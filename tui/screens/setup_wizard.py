"""Setup wizard — first run saat config belum ada (DESIGN §8 + PLAN-phase3).

Alur: Welcome → Provider → Base URL → API Key → Fetch Model →
Search (opsional) → Konfirmasi → simpan config.yaml → mulai app.

Dipakai main.py kalau file config tidak ada:
    from tui.screens.setup_wizard import run_setup_wizard
    run_setup_wizard(path)  # True = tersimpan, False = dibatalkan

fetch_models(provider_id, base, key) dipisah agar bisa di-mock di test.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static


@dataclass
class Provider:
    id: str
    label: str
    default_base: str = ""       # kosong = default SDK/provider
    needs_key: bool = True
    key_hint: str = ""
    recommended: str = ""        # model rekomendasi (fallback/panduan)


PROVIDERS: tuple[Provider, ...] = (
    Provider("anthropic", "Anthropic", "", True, "sk-ant-xxxx",
             "claude-sonnet-4-6"),
    Provider("openai", "OpenAI", "https://api.openai.com/v1", True, "sk-xxxx",
             "gpt-4o"),
    Provider("gemini", "Google Gemini", "", True, "AIzaxxxx",
             "gemini-2.0-flash"),
    Provider("groq", "Groq", "https://api.groq.com/openai/v1", True, "gsk_xxxx",
             "llama-3.3-70b-versatile"),
    Provider("ollama", "Ollama (local)", "http://localhost:11434", False, "",
             "llama3.2"),
    Provider("custom", "Custom (OpenAI-compatible)", "", True, "key-kamu", ""),
)

SEARCH_OPTIONS: tuple[tuple[str, str], ...] = (
    ("tavily", "Tavily (rekomendasi research)"),
    ("exa", "Exa"),
    ("brave", "Brave Search"),
    ("serpapi", "SerpAPI"),
    ("duckduckgo", "DuckDuckGo (gratis)"),
    ("skip", "Skip (nanti saja)"),
)


def prefix_model(provider_id: str, model: str) -> str:
    """'gpt-4o' + openai → 'openai/gpt-4o'. Sudah prefix → apa adanya."""
    model = model.strip()
    if "/" in model or provider_id == "custom":
        return model
    return f"{provider_id}/{model}"


def curated_models(provider_id: str) -> list[str]:
    """Daftar model kurasi instan (tanpa network) buat provider ini.

    Dipakai wizard biar step model langsung tampil — live fetch jalan
    paralel di background lalu merge. Custom → [] (ketik manual).
    """
    try:
        from tui.widgets.model_selector import CATALOG
    except Exception:
        return []
    want = {"anthropic": "Anthropic", "openai": "OpenAI",
            "gemini": "Google", "groq": "Groq",
            "ollama": "Ollama (local)"}.get(provider_id, "")
    return [n for p, ms in CATALOG for n, _ in ms if p == want]


def prev_step(step: int, *, needs_key: bool,
              search_key_shown: bool, telegram_on: bool) -> int:
    """Langkah mundur dari `step` (pure function, gampang dites).

    Melompati step kondisional yang tak ditampilkan (keyless ollama,
    search skip/duckduckgo, telegram skip). Step 5 (model) mundur ke
    pengisi key/base — maju lagi = kurasi instan + fetch ulang.
    """
    back = {
        1: 0,
        2: 1,
        3: 2,
        5: 3 if needs_key else 2,
        6: 5,
        7: 6,
        8: 7 if search_key_shown else 6,
        9: 8,
        10: 9,
        11: 10 if telegram_on else 8,
    }
    return back.get(step, step)


def fetch_models(provider_id: str, base: str, key: str,
                 timeout: int = 15) -> tuple[list[str], str]:
    """Ambil daftar model dari provider. Return (models, error).

    error kosong = sukses. Gagal (key salah/offline) → ([], pesan).
    Pure network, sync — dipanggil via to_thread.
    """
    try:
        if provider_id == "anthropic":
            resp = httpx.get(
                "https://api.anthropic.com/v1/models", timeout=timeout,
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
            resp.raise_for_status()
            return ([m["id"] for m in resp.json().get("data", []) if m.get("id")],
                    "")
        if provider_id == "gemini":
            resp = httpx.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": key}, timeout=timeout)
            resp.raise_for_status()
            out = []
            for m in resp.json().get("models", []):
                name = m.get("name", "").removeprefix("models/")
                if name:
                    out.append(name)
            return (out, "")
        # OpenAI-compatible (openai/groq/ollama/custom)
        roots = {"openai": "https://api.openai.com/v1",
                 "groq": "https://api.groq.com/openai/v1",
                 "ollama": "http://localhost:11434"}
        root = (base.strip() or roots.get(provider_id, "")).rstrip("/")
        if not root:
            return ([], "Base URL wajib diisi untuk provider custom.")
        headers = {} if provider_id == "ollama" else {
            "Authorization": f"Bearer {key}"}
        url = root + ("" if root.endswith("/v1") or "/v1" in root
                      else "/v1") + "/models"
        # root openai/groq sudah .../v1 → url tepat; ollama → +/v1? no:
        # ollama pakai /api/tags. Tangani khusus:
        if provider_id == "ollama":
            resp = httpx.get(root + "/api/tags", timeout=timeout)
            resp.raise_for_status()
            return ([m["name"] for m in resp.json().get("models", [])
                     if m.get("name")], "")
        resp = httpx.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return ([m["id"] for m in resp.json().get("data", []) if m.get("id")],
                "")
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            return ([], "API key ditolak (401/403) — cek key lalu coba lagi.")
        return ([], f"HTTP {e.response.status_code} dari provider.")
    except httpx.TimeoutException:
        return ([], "Timeout — cek koneksi internet.")
    except httpx.HTTPError as e:
        return ([], f"Gagal konek: {e}")
    except (ValueError, KeyError) as e:
        return ([], f"Response tak terduga: {e}")


class SetupWizard(Screen):
    """State machine wizard. Satu screen, body di-render ulang per step."""

    def __init__(self, save_path: Path) -> None:
        super().__init__()
        self.save_path = save_path
        self.step = 0
        self.provider: Provider = PROVIDERS[0]
        self.api_base = ""
        self.api_key = ""
        self.model = ""
        self.search_provider = "skip"
        self.search_api_key = ""
        self.telegram_enabled = False
        self.tg_token = ""
        self.tg_admin_id = ""
        self.tg_admin_username = ""
        self.models: list[str] = []
        self.fetch_error = ""
        self.fetch_models_fn = fetch_models  # mockable di test
        self._fetch_gen = 0  # batalkan fetch basi (user Back saat loading)

    def compose(self) -> ComposeResult:
        yield Static("multacd setup", id="wiz-title")
        yield Vertical(id="wiz-body")
        yield Static("", id="wiz-hint")

    def on_mount(self) -> None:
        self._show()

    # ── render per step ──
    def _body(self) -> Vertical:
        return self.query_one("#wiz-body", Vertical)

    async def _clear_body(self) -> None:
        body = self._body()
        for child in list(body.children):
            await child.remove()

    def _hint(self, text: str) -> None:
        with suppress(Exception):  # body belum mount saat init
            self.query_one("#wiz-hint", Static).update(text)

    def _show(self) -> None:
        self.run_worker(self._show_async())

    async def _show_async(self) -> None:
        await self._clear_body()
        body = self._body()
        if self.step == 0:
            await body.mount(Static("Welcome to multacd\n"
                                    "Agentic TUI for coding & research"))
            await body.mount(Static(
                f"Config belum ditemukan di {self.save_path}\n"
                "Mari setup dalam beberapa langkah."))
            await body.mount(Static("[ Enter ]  Continue"))
            self._hint("Enter lanjut · Esc kembali · Ctrl+C batal")
        elif self.step == 1:
            await body.mount(Static("Setup (1/6) — LLM Provider"))
            items = [ListItem(Label(f"{'> ' if p.id == self.provider.id else ''}"
                                    f"{p.label}")) for p in PROVIDERS]
            lv = ListView(*items, id="wiz-list")
            await body.mount(lv)
            lv.index = next(i for i, p in enumerate(PROVIDERS)
                            if p.id == self.provider.id)
            lv.focus()
            self._hint("Atas/Bawah pilih · Enter lanjut · Esc kembali")
        elif self.step == 2:
            await body.mount(Static(
                f"Setup (2/6) — API Base URL ({self.provider.label})\n"
                "Kosongkan untuk default." + (
                    f"\nDefault: {self.provider.default_base}"
                    if self.provider.default_base else "")))
            await body.mount(Input(
                value=self.api_base or self.provider.default_base,
                placeholder="https://... (kosong = default)", id="wiz-input"))
            self._hint("Enter lanjut · Esc kembali · Ctrl+C batal")
            self.query_one("#wiz-input", Input).focus()
        elif self.step == 3:
            await body.mount(Static(
                f"Setup (3/6) — API Key ({self.provider.label})"))
            await body.mount(Input(
                placeholder=self.provider.key_hint or "api key",
                password=True, id="wiz-input"))
            self._hint("Enter lanjut · Esc kembali · karakter disembunyikan")
            self.query_one("#wiz-input", Input).focus()
        elif self.step == 5:
            await body.mount(Static(
                "Setup (4/6) — Model" + (
                    f"\n! {self.fetch_error}" if self.fetch_error else "")))
            await body.mount(Input(
                placeholder=f"cth: {self.provider.recommended} "
                            "(atau pilih dari list kalau ada)",
                id="wiz-input"))
            if self.models:
                await body.mount(ListView(
                    *[ListItem(Label(m)) for m in self.models[:20]],
                    id="wiz-list"))
            else:
                # List kosong (custom provider) — wadah buat merge live.
                await body.mount(ListView(id="wiz-list"))
            self._hint("sinkron live... · Ketik manual lalu Enter · "
                       "klik list · Esc kembali")
            with suppress(Exception):
                self.query_one("#wiz-input", Input).focus()
        elif self.step == 6:
            await body.mount(Static(
                "Setup (5/6) — Search Provider (opsional)\n"
                "Buat mode /research. Boleh skip."))
            labels = [desc for _, desc in SEARCH_OPTIONS]
            search_lv = ListView(
                *[ListItem(Label(lbl)) for lbl in labels], id="wiz-list")
            await body.mount(search_lv)
            search_lv.focus()
            self._hint("Atas/Bawah pilih · Enter lanjut · Esc kembali")
        elif self.step == 7:
            need_key = (self.search_provider not in ("skip", "duckduckgo"))
            await body.mount(Static(
                f"Search key ({self.search_provider}) — "
                "kosongkan untuk lewati."))
            if need_key:
                await body.mount(Input(placeholder="search api key",
                                       password=True, id="wiz-input"))
                self.query_one("#wiz-input", Input).focus()
            else:
                await body.mount(Button("Lanjut [Enter]", id="wiz-next"))
            self._hint("Enter lanjut · Esc kembali")
        elif self.step == 8:
            await body.mount(Static(
                "Setup (6/6) — Telegram bot (opsional)\n"
                "Kontrol multacd dari HP. Bisa skip, isi nanti."))
            tg_lv = ListView(
                ListItem(Label("Ya, setup Telegram")),
                ListItem(Label("Skip (nanti saja)")), id="wiz-list")
            await body.mount(tg_lv)
            tg_lv.focus()
            self._hint("Atas/Bawah pilih · Enter lanjut · Esc kembali")
        elif self.step == 9:
            await body.mount(Static(
                "Telegram — bot token dari @BotFather\n"
                "Kosongkan untuk lewati."))
            await body.mount(Input(placeholder="123456:AAF...",
                                   password=True, id="wiz-input"))
            self.query_one("#wiz-input", Input).focus()
            self._hint("Enter lanjut · Esc kembali")
        elif self.step == 10:
            await body.mount(Static(
                "Telegram — user ID kamu (angka, dari @userinfobot)\n"
                "Format: 123456 [username opsional]. Kosongkan = lewati."))
            await body.mount(Input(placeholder="123456 usernamekamu",
                                   id="wiz-input"))
            self.query_one("#wiz-input", Input).focus()
            self._hint("Enter lanjut · Esc kembali")
        elif self.step == 11:
            tg_on = "ya" if self.telegram_enabled else "tidak"
            lines = [
                "Setup selesai", "",
                f"Provider  : {self.provider.label}",
                f"Model     : {self.model}",
                f"Search    : {self.search_provider}",
                f"Telegram  : {tg_on}",
                f"Config    : {self.save_path}", "",
            ]
            await body.mount(Static("\n".join(lines)))
            await body.mount(Button("Simpan & Mulai [Enter]", id="wiz-save"))
            await body.mount(Button("Ulangi Setup", id="wiz-restart"))
            self._hint("Enter simpan · Ctrl+C batal")
        # Tombol Kembali di semua step isi (kecuali welcome/final).
        # Termux tak selalu punya Esc — tombol ini yang utama di HP.
        if self.step not in (0, 11):
            await body.mount(Button("← Kembali [Esc]", id="wiz-back"))

    async def _to_model_step(self) -> None:
        """Masuk step model: kurasi instan langsung tampil, live paralel.

        Dulu: layar 'Fetching...' 15 dtk. Sekarang: list kurasi muncul
        seketika (bisa langsung pilih/ketik), fetch asli jalan di
        background lalu merge diam-diam kalau masih di step ini.
        """
        self.models = curated_models(self.provider.id)
        if not self.model and self.models:
            self.model = prefix_model(self.provider.id, self.models[0])
        self.fetch_error = ""
        self._fetch_gen += 1
        self.step = 5
        self._show()
        self.run_worker(self._load_models_live(self._fetch_gen))

    async def _load_models_live(self, gen: int) -> None:
        """Fetch live di background; merge ke list kalau user masih di sini."""
        base = self.api_base or self.provider.default_base
        models, err = await asyncio.to_thread(
            self.fetch_models_fn, self.provider.id, base, self.api_key)
        if gen != self._fetch_gen or self.step != 5:
            return  # basi: user pindah/back — buang
        if models and not err:
            self.models = models
            self.fetch_error = ""
            if not self.model:
                self.model = prefix_model(self.provider.id, models[0])
        else:
            self.fetch_error = err  # kurasi tetap tampil + notice error
        self._refresh_model_list()

    def _refresh_model_list(self) -> None:
        """Update ListView + hint di tempat (input ketikan user aman)."""
        try:
            lst = self.query_one("#wiz-list", ListView)
        except Exception:
            return
        with suppress(Exception):
            lst.clear()
            for m in self.models[:20]:
                lst.append(ListItem(Label(m)))
            if self.fetch_error:
                self._hint(f"live gagal ({self.fetch_error}) — list kurasi. "
                           "Esc kembali")
            elif self.models:
                self._hint("sinkron live · Ketik manual lalu Enter · klik list · "
                           "Esc kembali")

    def _back_args(self) -> dict[str, bool]:
        return {
            "needs_key": self.provider.needs_key,
            "search_key_shown": self.search_provider not in ("skip", "duckduckgo"),
            "telegram_on": self.telegram_enabled,
        }

    async def _prev(self) -> None:
        """Mundur satu langkah (Esc / tombol Kembali). Step 0: diam.

        Step 4 (fetching) boleh mundur — fetch basi dibuang via _fetch_gen.
        """
        if self.step == 0:
            return
        self._fetch_gen += 1  # batalkan fetch yang mungkin jalan
        self.step = prev_step(self.step, **self._back_args())
        self._show()

    # ── navigasi ──
    async def _next_from(self, value: str = "") -> None:
        if self.step == 0:
            self.step = 1
        elif self.step == 1:
            self.step = 2
            if not self.provider.needs_key:
                self.api_key = "none"  # ollama keyless, tetap bisa ubah base
        elif self.step == 2:
            self.api_base = value.strip()
            if not self.provider.needs_key:
                self.api_key = "none"  # ollama keyless, tetap bisa ubah base
                await self._to_model_step()
                return
            self.step = 3
        elif self.step == 3:
            if not value.strip():
                self._hint("API key wajib diisi (atau Ctrl+C batal).")
                return
            self.api_key = value.strip()
            await self._to_model_step()
            return
        elif self.step == 5:
            # List diklik → on_list_view_selected yang urus; Enter manual:
            if value.strip():
                self.model = prefix_model(self.provider.id, value.strip())
                self.step = 6
            elif self.models:
                self.model = prefix_model(self.provider.id, self.models[0])
                self.step = 6
            else:
                self._hint("Ketik nama model dulu (fetch gagal).")
                return
        elif self.step == 7:
            self.search_api_key = value.strip()
            self.step = 8
        elif self.step == 9:
            self.tg_token = value.strip()
            self.step = 10
        elif self.step == 10:
            # Format: "123456 [username]" — username opsional.
            parts = value.strip().split()
            self.tg_admin_id = parts[0] if parts else ""
            self.tg_admin_username = parts[1].lstrip("@") if len(parts) > 1 else ""
            self.step = 11
        self._show()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "wiz-back":
            await self._prev()
        elif event.button.id == "wiz-next":
            if self.step == 7:
                await self._next_from("")
            else:
                await self._next_from()
        elif event.button.id == "wiz-save":
            self._save()
        elif event.button.id == "wiz-restart":
            self.step = 0
            self._show()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "wiz-input":
            await self._next_from(event.value)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        try:
            lst = self.query_one("#wiz-list", ListView)
            idx = list(lst.children).index(event.item)
        except ValueError:
            return
        if self.step == 1:
            self.provider = PROVIDERS[idx]
            await self._next_from()
        elif self.step == 5 and self.models:
            self.model = prefix_model(self.provider.id, self.models[idx])
            self.step = 6
            self._show()
        elif self.step == 6:
            self.search_provider = SEARCH_OPTIONS[idx][0]
            self.step = 8 if self.search_provider in ("skip", "duckduckgo") \
                else 7
            self._show()
        elif self.step == 8:
            self.telegram_enabled = (idx == 0)
            self.step = 9 if self.telegram_enabled else 11
            self._show()

    def _save(self) -> None:
        from core.config import Config

        data: dict[str, Any] = {
            "model": self.model,
            "api_key": self.api_key,
        }
        base = self.api_base.strip() or self.provider.default_base
        if base.strip():
            data["api_base"] = base.strip()
        if self.search_provider != "skip":
            data["search_provider"] = self.search_provider
            data["search_api_key"] = self.search_api_key
        if self.telegram_enabled and (self.tg_token or self.tg_admin_id):
            tg: dict[str, Any] = {}
            if self.tg_token:
                tg["bot_token"] = self.tg_token
            if self.tg_admin_id:
                try:
                    tg["admin_id"] = int(self.tg_admin_id)
                except ValueError:
                    self._hint("Admin ID harus angka — Telegram di-skip.")
                    tg.pop("admin_id", None)
            if self.tg_admin_username:
                tg["admin_username"] = self.tg_admin_username
            if tg:
                data["telegram"] = tg
        try:
            Config(**data)
        except Exception as e:
            self._hint(f"Config tidak valid: {e}")
            return
        try:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.save_path, "w", encoding="utf-8") as fh:
                yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)
        except OSError as e:
            self._hint(f"Gagal tulis config: {e}")
            return
        app = self.app
        if hasattr(app, "setup_result"):
            app.setup_result = data
        app.exit()

    async def on_key(self, event: events.Key) -> None:
        # Enter di list provider (step 1/6): ListView sudah handle select
        # sendiri; Enter di body lain = tombol utama.
        if event.key == "enter" and self.step == 0:
            event.prevent_default()
            event.stop()
            await self._next_from()
        elif event.key == "escape":
            event.prevent_default()
            event.stop()
            await self._prev()


class SetupApp(App[None]):
    """App sekali pakai buat wizard. Hasil di setup_result (None = batal)."""

    BINDINGS = [
        ("ctrl+c", "cancel", "Batal"),
        ("ctrl+q", "cancel", "Batal"),
    ]

    def __init__(self, save_path: Path) -> None:
        super().__init__()
        self.setup_result: dict[str, Any] | None = None
        self._save_path = save_path

    async def on_mount(self) -> None:
        # Wizard adalah Screen penuh (di-push, bukan di-yield di compose —
        # Screen tidak bisa jadi child widget).
        self.push_screen(SetupWizard(self._save_path))

    def action_cancel(self) -> None:
        self.setup_result = None
        self.exit()


def run_setup_wizard(save_path: Path) -> dict[str, Any] | None:
    """Jalankan wizard (blocking). Return data config atau None (batal)."""
    app = SetupApp(save_path)
    app.run()
    return app.setup_result


if __name__ == "__main__":
    # Pure logic (network dimock di pilot).
    assert prefix_model("openai", "gpt-4o") == "openai/gpt-4o"
    assert prefix_model("openai", "openai/gpt-4o") == "openai/gpt-4o"
    assert prefix_model("custom", "mymodel") == "mymodel"
    assert prefix_model("ollama", "llama3.2") == "ollama/llama3.2"
    assert len(PROVIDERS) == 6 and len(SEARCH_OPTIONS) == 6
    assert PROVIDERS[0].id == "anthropic"
    assert not PROVIDERS[4].needs_key  # ollama keyless
    # Back-nav: lompati step kondisional yang tak tampil.
    full = {"needs_key": True, "search_key_shown": True, "telegram_on": True}
    assert [prev_step(s, **full) for s in (1, 2, 3, 5, 6, 8, 11)] == \
        [0, 1, 2, 3, 5, 7, 10]
    assert prev_step(7, **full) == 6
    assert prev_step(9, **full) == 8 and prev_step(10, **full) == 9
    skip = {"needs_key": False, "search_key_shown": False,
            "telegram_on": False}
    assert prev_step(5, **skip) == 2
    assert prev_step(8, **skip) == 6 and prev_step(11, **skip) == 8
    assert prev_step(0, **full) == 0  # mentok, diam
    # Kurasi instan: per provider tanpa network; custom → manual.
    assert curated_models("groq") == ["llama-3.3-70b-versatile",
                                      "llama-3.1-8b-instant"]
    assert curated_models("ollama") == ["llama3.2", "qwen2.5-coder"]
    assert curated_models("custom") == []
    print("✅ setup_wizard self-test OK (prefix + metadata + back-nav)")
