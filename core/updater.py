"""Auto-update — cek versi PyPI sekali sehari, silent kalau gagal.

Alur:
    check() → baca cache ~/.multacd/update_check.json
              cache segar (<24 jam) → pakai tanpa network
              else → httpx ke PyPI (gagal = None, jangan ganggu user)

Dipanggil TUI via asyncio.to_thread (tidak block startup) dan CLI
`multacd update` (sebenarnya pip install --upgrade).

Test cepat:
    python -m core.updater
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

PYPI_URL = "https://pypi.org/pypi/multacd/json"
CHECK_INTERVAL_HOURS = 24
# Source checkout (belum pip install) → metadata tak ada → pakai ini.
# Disatukan dengan tui.app.APP_VERSION saat Step 4 (entry point).
FALLBACK_VERSION = "0.0.0-beta"


def update_cache_file() -> Path:
    """Path cache — dinamis hormati MULTACD_HOME (buat test)."""
    home = Path(os.environ.get("MULTACD_HOME", str(Path.home())))
    return home / ".multacd" / "update_check.json"


def get_current_version() -> str:
    """Versi terinstall (metadata) atau fallback dev."""
    try:
        from importlib.metadata import version
        return version("multacd")
    except Exception:
        return FALLBACK_VERSION


def get_latest_version(timeout: int = 10) -> str | None:
    """Versi terbaru di PyPI. None kalau network gagal — silent."""
    try:
        import httpx
        resp = httpx.get(PYPI_URL, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        ver = data.get("info", {}).get("version")
        return str(ver) if ver else None
    except Exception:
        return None


def _parse_version(v: str) -> tuple[tuple[int, ...], str]:
    """'1.2.0-beta' → ((1,2,0), 'beta'). 'v' depan dimaafkan."""
    v = (v or "").strip().lstrip("vV")
    m = re.match(r"^(\d+(?:\.\d+)*)(.*)$", v)
    if not m:
        return (), v
    nums = tuple(int(x) for x in m.group(1).split("."))
    return nums, m.group(2).strip(".-+ ")


def is_newer(latest: str, current: str) -> bool:
    """True kalau latest lebih baru. Release > prerelease di angka sama."""
    try:
        ln, ls = _parse_version(latest)
        cn, cs = _parse_version(current)
        if not ln or not cn:
            return False
        width = max(len(ln), len(cn))
        ln += (0,) * (width - len(ln))
        cn += (0,) * (width - len(cn))
        if ln != cn:
            return ln > cn
        if not ls and cs:
            return True
        if ls and not cs:
            return False
        return ls > cs
    except Exception:
        return False


def _read_cache() -> dict[str, Any]:
    try:
        raw = update_cache_file().read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _cache_fresh(cached: dict[str, Any]) -> bool:
    try:
        checked = _dt.datetime.fromisoformat(str(cached["checked_at"]))
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=_dt.timezone.utc)
        age = _dt.datetime.now(_dt.timezone.utc) - checked
        return age < _dt.timedelta(hours=CHECK_INTERVAL_HOURS)
    except Exception:
        return False


def _write_cache(latest: str) -> None:
    try:
        path = update_cache_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "checked_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "latest_version": latest,
        }), encoding="utf-8")
    except Exception:
        pass  # cache gagal ditulis bukan alasan ganggu user


def check(fetch: Callable[[], str | None] | None = None) -> dict[str, Any]:
    """Orchestrate: return {update_available, latest_version, current_version}.

    `fetch` = injeksi buat test (default: get_latest_version).
    Tidak pernah raise.
    """
    try:
        current = get_current_version()
        cached = _read_cache()
        latest: str | None = None
        if _cache_fresh(cached):
            latest = cached.get("latest_version")
        if not latest:
            try:
                latest = (fetch or get_latest_version)()
            except Exception:
                latest = None
            if latest:
                _write_cache(latest)
            elif cached.get("latest_version"):
                latest = cached.get("latest_version")  # cache basi tetap hint
        return {
            "update_available": bool(latest) and is_newer(latest, current),
            "latest_version": latest,
            "current_version": current,
        }
    except Exception:
        return {"update_available": False, "latest_version": None,
                "current_version": get_current_version()}


if __name__ == "__main__":
    import tempfile

    # 1. Pure compare.
    assert is_newer("1.0.0", "0.9.9")
    assert is_newer("1.0.0", "1.0.0-beta")
    assert not is_newer("1.0.0-beta", "1.0.0")
    assert not is_newer("1.0.0", "1.0.0")
    assert not is_newer("0.9.0", "1.0.0")
    assert is_newer("1.0.1", "1.0.0")
    assert is_newer("v1.1.0", "1.0.9")
    assert not is_newer("ngawur", "1.0.0")
    assert not is_newer("1.0.0", "ngawur")

    # 2. check() dengan fetch injeksi (tanpa network).
    with tempfile.TemporaryDirectory() as home:
        os.environ["MULTACD_HOME"] = home
        try:
            r = check(fetch=lambda: "99.0.0")
            assert r["update_available"] and r["latest_version"] == "99.0.0", r
            # Kedua: cache segar → fetch tidak dipanggil (naik = bocor).
            def _boom() -> str | None:
                raise AssertionError("network kepanggil padahal cache segar")
            r2 = check(fetch=_boom)
            assert r2["update_available"] and r2["latest_version"] == "99.0.0", r2
            assert update_cache_file().is_file()
            # Fetch gagal total + cache dihapus → silent, bukan raise.
            update_cache_file().unlink()
            r3 = check(fetch=lambda: (_ for _ in ()).throw(RuntimeError("offline")))
            assert r3 == {"update_available": False, "latest_version": None,
                          "current_version": r3["current_version"]}, r3
        finally:
            del os.environ["MULTACD_HOME"]

    print("✅ updater self-test OK (compare + cache + silent-fail)")
