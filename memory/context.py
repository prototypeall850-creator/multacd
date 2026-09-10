"""Short-term memory — history pesan dalam satu sesi.

Format message mengikuti konvensi OpenAI/LiteLLM:
    {"role": "user" | "assistant" | "system" | "tool", "content": ...}

Test cepat:
    python -m memory.context
"""

from __future__ import annotations

import json
from typing import Any


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


class ConversationContext:
    """Simpan messages sebagai list Python biasa (satu sesi = satu instance)."""

    def __init__(self, system_prompt: str | None = None) -> None:
        self._messages: list[dict[str, Any]] = []
        if system_prompt:
            self.add_message("system", system_prompt)

    def add_message(self, role: str, content: str) -> None:
        """Tambah pesan mentah (user / assistant / system)."""
        if not role or content is None:
            raise ValueError("role dan content wajib diisi")
        self._messages.append({"role": role, "content": content})

    def add_tool_result(self, tool_call_id: str, tool_name: str, result: dict[str, Any]) -> None:
        """Tambah hasil tool ke history dengan format yang ramah LLM."""
        if result.get("success"):
            content = _stringify(result.get("result"))
        else:
            content = f"Error menjalankan {tool_name}: {result.get('error')}"
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content,
        })

    def add_assistant_tool_calls(self, text: str, calls: list[Any]) -> None:
        """Tambah pesan assistant yang memanggil tool (format OpenAI).

        `calls` berisi object dengan atribut id/name/arguments
        (mis. ToolCallRequest dari core.llm_client). Wajib ada agar
        provider tidak 400 pada turn berikutnya (tool_call_id harus
        merujuk ke assistant message sebelumnya).
        """
        import json as _json

        self._messages.append({
            "role": "assistant",
            "content": text or None,
            "tool_calls": [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": _json.dumps(c.arguments, ensure_ascii=False)},
                }
                for c in calls
            ],
        })

    def get_messages(self) -> list[dict[str, Any]]:
        """Return semua messages (copy list — jangan mutasi hasilnya)."""
        return list(self._messages)

    def clear(self) -> None:
        """Kosongkan history (mulai sesi baru)."""
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)


if __name__ == "__main__":
    ctx = ConversationContext(system_prompt="kamu asisten")
    assert ctx.get_messages() == [{"role": "system", "content": "kamu asisten"}]

    ctx.add_message("user", "halo")
    ctx.add_tool_result("call_1", "read_file", {"success": True, "result": "isi", "error": None})
    ctx.add_tool_result("call_2", "bash", {"success": False, "result": None, "error": "timeout"})
    ctx.add_tool_result("call_3", "read_many_files",
                        {"success": True, "result": {"a.py": "x"}, "error": None})
    msgs = ctx.get_messages()
    assert [m["role"] for m in msgs] == ["system", "user", "tool", "tool", "tool"], msgs
    assert msgs[2] == {"role": "tool", "tool_call_id": "call_1",
                       "name": "read_file", "content": "isi"}, msgs[2]
    assert "timeout" in msgs[3]["content"] and "bash" in msgs[3]["content"], msgs[3]
    assert '"a.py"' in msgs[4]["content"], msgs[4]  # dict di-JSON-kan

    # get_messages return copy — mutasi hasil tidak merusak internal
    msgs.append({"role": "user", "content": "nakal"})
    assert len(ctx) == 5

    try:
        ctx.add_message("", "x")
    except ValueError:
        pass
    else:
        raise AssertionError("role kosong harus ditolak")

    ctx.clear()
    assert ctx.get_messages() == [] and len(ctx) == 0

    print("✅ memory context self-test OK")
