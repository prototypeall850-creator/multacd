"""Query generator — LLM bikin search queries beragam dari satu topik.

Tiga fungsi (lihat PLAN-phase3 Step 4):
  generate_quick_queries     3 sudut: definisi, perbandingan, aplikasi terbaru
  generate_deep_queries      broad, buat round pertama deep research
  generate_followup_queries  spesifik, dari findings+gaps round sebelumnya

Semua async, terima `llm` duck-typed (punya .complete(messages)).
Tanpa `llm` → setup dari config (butuh ~/.multacd/config.yaml).
Selalu return ≥1 query (fallback = topik itu sendiri) supaya
orchestrator tidak pernah deadlock.

Test cepat:
    python -m core.research.query_generator
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_ARRAY_RE = re.compile(r"\[.*?\]", re.DOTALL)


def parse_queries(text: str, n: int, topic: str) -> list[str]:
    """Ambil JSON array dari response LLM. Pure function.

    Tahan banting: fence code, teks pembungkus, sampai garbage total
    (fallback: baris non-kosong, terakhir: topik itu sendiri).
    """
    candidates: list[str] = []
    m = _FENCE_RE.search(text)
    block = m.group(1) if m else text
    try:
        data = json.loads(block.strip())
        if isinstance(data, list):
            candidates = [str(x) for x in data]
    except (json.JSONDecodeError, ValueError):
        m2 = _ARRAY_RE.search(block)
        if m2:
            try:
                data = json.loads(m2.group(0))
                if isinstance(data, list):
                    candidates = [str(x) for x in data]
            except (json.JSONDecodeError, ValueError):
                pass
    if not candidates:
        # Fallback: baris non-kosong, buang bullet/numbering.
        for line in text.splitlines():
            line = re.sub(r"^[\s>\-*•\d.)]+", "", line).strip().strip("\"'")
            if len(line) > 3:
                candidates.append(line)
    # Bersihkan: unik, non-kosong, maksimal n.
    seen: set[str] = set()
    out: list[str] = []
    for q in candidates:
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
        if len(out) >= n:
            break
    return out or [topic.strip()]


async def _ask(llm: Any, prompt: str, topic: str, n: int) -> list[str]:
    """Kirim prompt, parse response. LLM error → fallback [topic]."""
    from core.llm_client import LLMError

    try:
        done = await llm.complete([{"role": "user", "content": prompt}])
        return parse_queries(done.text or "", n, topic)
    except LLMError:
        return [topic.strip()]
    except Exception:
        return [topic.strip()]


def _base_instruction(n: int) -> str:
    return (
        f"Generate {n} search queries. Return HANYA JSON array of strings, "
        "tanpa penjelasan lain. Query dalam bahasa yang sama dengan topik."
    )


async def generate_quick_queries(topic: str, n: int = 3,
                                 llm: Any = None) -> list[str]:
    """3 sudut pandang: definisi dasar, perbandingan/konteks, aplikasi terbaru."""
    if not topic.strip():
        return []
    llm = llm or _default_llm()
    prompt = (
        f"Topik: {topic}\n{_base_instruction(n)}\n"
        f"Query 1: definisi/penjelasan dasar. Query 2: perbandingan/konteks "
        f"lebih luas. Query 3: aplikasi/contoh praktis terbaru."
    )
    return await _ask(llm, prompt, topic, n)


async def generate_deep_queries(topic: str, n: int = 4,
                                llm: Any = None) -> list[str]:
    """Broad queries buat round pertama deep research."""
    if not topic.strip():
        return []
    llm = llm or _default_llm()
    prompt = (
        f"Topik: {topic}\n{_base_instruction(n)}\n"
        "Queries harus broad dan mencakup aspek berbeda dari topik "
        "(latar belakang, perkembangan terkini, perdebatan, implikasi)."
    )
    return await _ask(llm, prompt, topic, n)


async def generate_followup_queries(topic: str, findings: str, gaps: str,
                                    n: int = 4, llm: Any = None) -> list[str]:
    """Queries spesifik dari gaps round sebelumnya."""
    if not topic.strip():
        return []
    llm = llm or _default_llm()
    prompt = (
        f"Topik: {topic}\n"
        f"Temuan sejauh ini:\n{findings}\n\n"
        f"Aspek yang masih gelap:\n{gaps}\n\n"
        f"{_base_instruction(n)}\n"
        "Queries harus spesifik dan targeted untuk menutup gaps di atas, "
        "bukan mengulang yang sudah diketahui."
    )
    return await _ask(llm, prompt, topic, n)


def _default_llm() -> Any:
    from core.config import get_active_config, load_config
    from core.llm_client import setup_client
    # Active config sesi (Bug 3) — hormati --config & /model.
    return setup_client(get_active_config() or load_config())


if __name__ == "__main__":
    from core.llm_client import LLMError, StreamDone

    class FakeLLM:
        def __init__(self, text=None, error=None):
            self.text = text
            self.error = error
            self.last_prompt = ""

        async def complete(self, messages):
            self.last_prompt = messages[0]["content"]
            if self.error:
                raise self.error
            return StreamDone(self.text, [])

    async def _run() -> None:
        # 1. JSON bersih
        llm = FakeLLM('["q1 definisi", "q2 banding", "q3 aplikasi"]')
        out = await generate_quick_queries("topik X", n=3, llm=llm)
        assert out == ["q1 definisi", "q2 banding", "q3 aplikasi"], out
        assert "definisi" in llm.last_prompt and "topik X" in llm.last_prompt

        # 2. Dalam fence + teks pembungkus
        llm = FakeLLM('Ini queries:\n```json\n["a", "b"]\n```\nSemoga membantu.')
        assert await generate_quick_queries("t", n=3, llm=llm) == ["a", "b"]

        # 3. Garbage total → fallback baris
        llm = FakeLLM("bukan json sama sekali\nbaris kedua cukup panjang")
        out = await generate_quick_queries("topik Y", n=3, llm=llm)
        assert len(out) >= 1, out

        # 4. Kosong total → fallback topik (orchestrator tidak deadlock)
        llm = FakeLLM("")
        assert await generate_quick_queries("topik Z", llm=llm) == ["topik Z"]

        # 5. LLM error → fallback topik
        llm = FakeLLM(error=LLMError("rate limit"))
        assert await generate_deep_queries("topik W", llm=llm) == ["topik W"]

        # 6. Dedup + cap n
        llm = FakeLLM('["sama", "SAMA ", "unik1", "unik2"]')
        out = await generate_quick_queries("t", n=2, llm=llm)
        assert out == ["sama", "unik1"], out

        # 7. Topic kosong → list kosong (bukan fallback aneh)
        assert await generate_quick_queries("  ", llm=FakeLLM("x")) == []

        # 8. Followup pakai findings+gaps di prompt
        llm = FakeLLM('["f1", "f2"]')
        out = await generate_followup_queries("T", findings="tahu A",
                                              gaps="gelap B", llm=llm)
        assert out == ["f1", "f2"]
        assert "gelap B" in llm.last_prompt and "tahu A" in llm.last_prompt

        # 9. parse_queries pure: array di tengah teks tanpa fence
        assert parse_queries('bla ["p", "q"] bla', 5, "T") == ["p", "q"]

    asyncio.run(_run())
    print("✅ query_generator self-test OK (9 skenario)")
