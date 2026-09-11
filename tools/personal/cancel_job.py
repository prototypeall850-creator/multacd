"""cancel_job — hapus scheduled job. ASK-REQUIRED.

Test cepat:
    python -m tools.personal.cancel_job
"""

from __future__ import annotations

from typing import Any

from tools.common import fail, ok

SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "cancel_job",
        "description": "Hapus job terjadwal by name.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
}


def cancel_job(name: str) -> dict[str, Any]:
    from scheduler.engine import get_engine

    if not (name or "").strip():
        return fail("name tidak boleh kosong.")
    if get_engine().remove_job(name.strip()):
        return ok(f"Job '{name.strip()}' dihapus.")
    return fail(f"Job '{name.strip()}' tidak ada.")


if __name__ == "__main__":
    import os
    import tempfile

    from scheduler.engine import reset_engine
    from tools.personal.schedule_job import schedule_job

    with tempfile.TemporaryDirectory() as home:
        os.environ["MULTACD_HOME"] = home
        reset_engine()
        assert schedule_job("t", "0 7 * * *")["success"]
        assert cancel_job("t")["success"]
        r = cancel_job("t")
        assert not r["success"] and "tidak ada" in r["error"]
        assert not cancel_job("")["success"]
        reset_engine()
        del os.environ["MULTACD_HOME"]

    print("✅ cancel_job self-test OK (hapus + missing)")
