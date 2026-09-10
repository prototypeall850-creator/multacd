"""Prompt composer — susun system prompt dari soul + context + mode + rules.

Urutan komposisi final (lengkap di Phase 2 Step 7):
    [1] soul → [2] project_ctx → [3] mode_prompt → [4] operational rules

Step 1 ini: load_soul() + skeleton PromptComposer (project/mode diisi step berikutnya).

Test cepat:
    python -m core.prompt_composer
"""

from __future__ import annotations

import os
from pathlib import Path

FALLBACK_SOUL = "Kamu multacd, coding agent di terminal. Jawab singkat dan padat."

# Aturan teknis yang selalu berlaku (bagian [4]).
# NOTE: duplikasi sementara dengan SYSTEM_PROMPT di core/agent_loop.py —
# Step 7 menyatukan keduanya (agent_loop pakai composer, bukan hardcoded).
OPERATIONAL_RULES = (
    "Operational rules: gunakan tool yang tersedia untuk mengerjakan tugas; "
    "baca file dulu sebelum mengedit; "
    "kalau hasil tool berisi 'Dibatalkan user', hormati itu dan cari cara lain; "
    "jangan panggil tool yang tidak ada di daftar; "
    "jangan cetak JSON mentah ke user."
)


def config_dir() -> Path:
    base = Path(os.environ.get("MULTACD_HOME", str(Path.home())))
    return base / ".multacd"


def load_soul(config_path: Path | str | None = None,
              project_dir: Path | str | None = None) -> str:
    """Load soul.md dengan prioritas:
    1. ~/.multacd/soul.md (custom user)
    2. {project_dir}/soul.md (bawaan project)
    3. FALLBACK_SOUL (kalau keduanya tidak ada)
    """
    candidates: list[Path] = []
    if config_path is not None:
        candidates.append(Path(config_path).expanduser())
    else:
        candidates.append(config_dir() / "soul.md")
    if project_dir is not None:
        candidates.append(Path(project_dir).expanduser() / "soul.md")
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if text.strip():
            return text
    return FALLBACK_SOUL


class PromptComposer:
    """Skeleton — menampung bagian prompt; komposisi penuh di Step 7."""

    def __init__(self, soul: str = "") -> None:
        self.soul = soul or FALLBACK_SOUL
        self.project_ctx = ""   # diisi Step 3 (codebase scan)
        self.mode_prompt = ""   # diisi Step 2/7 (mode manager)

    def update_project_ctx(self, new_ctx: str) -> None:
        self.project_ctx = new_ctx

    def update_mode(self, new_mode_prompt: str) -> None:
        self.mode_prompt = new_mode_prompt

    def compose(self) -> str:
        parts = [self.soul]
        if self.project_ctx:
            parts.append(self.project_ctx)
        if self.mode_prompt:
            parts.append(self.mode_prompt)
        parts.append(OPERATIONAL_RULES)
        return "\n\n".join(parts)


if __name__ == "__main__":
    import tempfile

    project_root = Path(__file__).resolve().parent.parent

    # 1. Default: baca soul.md bawaan project
    soul = load_soul(project_dir=project_root)
    assert "multacd" in soul and "Cara bicara" in soul, soul[:100]

    # 2. Custom user menang atas bawaan (isolated home)
    tmp_home = tempfile.mkdtemp(prefix="multacd-soul-")
    os.environ["MULTACD_HOME"] = tmp_home
    try:
        custom = Path(tmp_home) / ".multacd" / "soul.md"
        custom.parent.mkdir(parents=True, exist_ok=True)
        custom.write_text("soul custom user", encoding="utf-8")
        assert load_soul(project_dir=project_root) == "soul custom user"
    finally:
        del os.environ["MULTACD_HOME"]

    # 3. Keduanya tidak ada → fallback (tidak crash)
    empty = tempfile.mkdtemp(prefix="multacd-empty-")
    assert load_soul(config_path=Path(empty) / "soul.md",
                     project_dir=empty) == FALLBACK_SOUL

    # 4. Composer skeleton: urutan soul → rules
    pc = PromptComposer(soul="S")
    prompt = pc.compose()
    assert prompt.index("S") < prompt.index("Operational rules"), prompt
    pc.update_project_ctx("CTX")
    pc.update_mode("MODE")
    prompt = pc.compose()
    assert [prompt.index(x) for x in ("S", "CTX", "MODE", "Operational rules")] == sorted(
        [prompt.index(x) for x in ("S", "CTX", "MODE", "Operational rules")])

    print("✅ prompt_composer self-test OK (load_soul prioritas + skeleton)")
