"""Codebase awareness — scan project biar agent langsung ngerti konteks.

    from core.codebase import scan_project, project_label

    ctx = scan_project(".")   # → string ProjectContext buat system prompt

Aturan scan (PLAN Phase 2 Section 5):
- SELALU: struktur folder (depth 3), file kunci root, entry point, git info.
- SKIP: file planning (PLAN*.md, ROADMAP.md, soul.md), dependency folder
  (.venv, node_modules), compiled (__pycache__, *.pyc), .git, secrets
  (.env), folder plan/ + roadmap/, pola di .gitignore.
- Gagal scan (I/O, git hilang) → fallback, tidak crash.

Test cepat:
    python -m core.codebase
"""

from __future__ import annotations

import subprocess
from pathlib import Path

TREE_DEPTH = 3
MAX_TREE_ENTRIES = 200
MAX_FILE_CHARS = 1500

# File kunci yang dibaca isinya (kalau ada di root).
KEY_FILES = (
    "README.md",
    ".env.example",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Makefile",
    "docker-compose.yml",
)

# File planning/bawaan — isi tidak relevan buat konteks kode.
SKIP_FILES = frozenset({"soul.md"})

SKIP_DIRS = frozenset({
    ".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
    ".idea", ".vscode", "dist", "build", "htmlcov",
    "plan", "roadmap",
})

SECRET_SUFFIXES = (".key", ".pem")

ENTRY_CANDIDATES = ("main.py", "app.py", "run.py", "index.py")


def _is_planning_file(name: str) -> bool:
    upper = name.upper()
    return upper == "PLAN.MD" or upper.startswith("PLAN-") or upper.startswith("PLAN_") \
        or upper == "ROADMAP.MD" or upper.startswith("ROADMAP-") or upper.startswith("ROADMAP_")


def detect_project_type(root: Path | str) -> str:
    """Tebak jenis project dari file signature di root."""
    root = Path(root)
    if list(root.glob("requirements.txt")) or list(root.glob("pyproject.toml")) \
            or list(root.glob("setup.py")) or list(root.glob("setup.cfg")):
        return "Python"
    if (root / "package.json").is_file():
        return "Node.js"
    if (root / "go.mod").is_file():
        return "Go"
    if (root / "Cargo.toml").is_file():
        return "Rust"
    if (root / "pom.xml").is_file() or list(root.glob("build.gradle*")):
        return "Java"
    return "Generic"


def _gitignore_names(root: Path) -> set[str]:
    """Parse .gitignore seperlunya: ambil pola nama sederhana."""
    names: set[str] = set()
    try:
        text = (root / ".gitignore").read_text(encoding="utf-8")
    except OSError:
        return names
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        line = line.strip("/").split("/")[0]
        if line and "*" not in line:
            names.add(line)
    return names


def build_file_tree(root: Path | str, depth: int = TREE_DEPTH) -> str:
    """Render struktur folder sebagai string tree (depth terbatas)."""
    root = Path(root)
    ignored = _gitignore_names(root)
    lines: list[str] = []
    count = 0
    truncated = False

    def skip_dir(d: Path) -> bool:
        return d.name in SKIP_DIRS or d.name in ignored or d.name.startswith(".")

    def skip_file(f: Path) -> bool:
        n = f.name
        return (
            n in SKIP_FILES or _is_planning_file(n) or n in ignored
            or n.startswith(".") or n.endswith(".pyc")
            or n == ".env" or n.endswith(SECRET_SUFFIXES)
        )

    def walk(dir_path: Path, prefix: str, level: int) -> None:
        nonlocal count, truncated
        if level > depth or truncated:
            return
        try:
            entries = sorted(dir_path.iterdir(),
                             key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return
        for p in entries:
            if count >= MAX_TREE_ENTRIES:
                truncated = True
                return
            if p.is_dir():
                if skip_dir(p):
                    continue
                lines.append(f"{prefix}{p.name}/")
                count += 1
                walk(p, prefix + "  ", level + 1)
            else:
                if skip_file(p):
                    continue
                lines.append(f"{prefix}{p.name}")
                count += 1

    if not root.is_dir():
        return "(folder tidak ditemukan)"
    walk(root, "", 1)
    if truncated:
        lines.append(f"… (dipotong, >{MAX_TREE_ENTRIES} entri)")
    return "\n".join(lines) if lines else "(folder kosong)"


def get_key_files(root: Path | str) -> dict[str, str]:
    """Baca file kunci root. File hilang → skip; isi dipotong MAX_FILE_CHARS."""
    root = Path(root)
    out: dict[str, str] = {}
    for name in KEY_FILES:
        try:
            text = (root / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if len(text) > MAX_FILE_CHARS:
            text = text[:MAX_FILE_CHARS] + "\n…(dipotong)"
        out[name] = text
    return out


def get_entry_points(root: Path | str) -> list[str]:
    root = Path(root)
    return [c for c in ENTRY_CANDIDATES if (root / c).is_file()]


def get_git_summary(root: Path | str) -> dict[str, object]:
    """Ringkasan git via subprocess. Bukan repo → {"is_repo": False}."""
    root = Path(root)
    try:
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            capture_output=True, text=True, timeout=5)
        if branch.returncode != 0:
            return {"is_repo": False}
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return {"is_repo": False}
    modified = untracked = 0
    if status.returncode == 0:
        for line in status.stdout.splitlines():
            if line.startswith("??"):
                untracked += 1
            elif line.strip():
                modified += 1
    return {
        "is_repo": True,
        "branch": branch.stdout.strip() or "(detached)",
        "modified": modified,
        "untracked": untracked,
    }


def _parse_dependencies(key_files: dict[str, str]) -> str:
    req = key_files.get("requirements.txt", "")
    names: list[str] = []
    for line in req.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", ";", "["):
            line = line.split(sep)[0]
        line = line.strip()
        if line:
            names.append(line)
    if names:
        shown = ", ".join(names[:12])
        return shown + ("…" if len(names) > 12 else "")
    if "pyproject.toml" in key_files:
        return "(lihat pyproject.toml)"
    if "package.json" in key_files:
        return "(lihat package.json)"
    return "-"


def scan_project(root: Path | str = ".") -> str:
    """Scan project → string ProjectContext (tidak pernah raise)."""
    try:
        return _scan_project(Path(root).expanduser())
    except Exception as e:
        return f"Project: (scan gagal: {type(e).__name__}: {e})"


def _scan_project(root: Path) -> str:
    name = root.resolve().name
    ptype = detect_project_type(root)
    key_files = get_key_files(root)
    tree = build_file_tree(root)
    entries = get_entry_points(root)
    git = get_git_summary(root)

    readme = key_files.get("README.md", "").replace("\n", " ").strip()
    readme = (readme[:500] + "…") if len(readme) > 500 else (readme or "-")

    if git.get("is_repo"):
        git_line = (f"branch '{git['branch']}', "
                    f"{git['modified']} modified, {git['untracked']} untracked")
    else:
        git_line = "bukan git repo"

    return (
        f"Project: {name}\n"
        f"Type: {ptype}\n"
        f"Entry point: {', '.join(entries) if entries else '-'}\n"
        f"Dependencies: {_parse_dependencies(key_files)}\n"
        f"Structure:\n{tree}\n"
        f"Git: {git_line}\n"
        f"README: {readme}"
    )


def project_label(root: Path | str = ".") -> str:
    """Label satu baris buat status/welcome: `nama · Tipe · branch +M ~U`."""
    root = Path(root)
    git = get_git_summary(root)
    if git.get("is_repo"):
        return (f"{root.resolve().name} · {detect_project_type(root)} · "
                f"{git['branch']} +{git['modified']} ~{git['untracked']}")
    return f"{root.resolve().name} · {detect_project_type(root)}"


if __name__ == "__main__":
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="multacd-codebase-"))
    (tmp / "README.md").write_text("# Demo\nProject contoh untuk test.\n" * 5)
    (tmp / "requirements.txt").write_text("textual>=8\nlitellm==1.100.0\n# komen\n")
    (tmp / "main.py").write_text("print('hi')\n")
    (tmp / "PLAN.md").write_text("planning, harus di-skip")
    (tmp / "soul.md").write_text("kepribadian, harus di-skip")
    (tmp / ".env").write_text("SECRET=xxx")
    (tmp / ".venv").mkdir()
    (tmp / ".venv" / "x.py").write_text("dep, harus di-skip")
    (tmp / "__pycache__").mkdir()
    (tmp / "__pycache__" / "a.pyc").write_bytes(b"\x00")
    (tmp / "plan").mkdir()
    (tmp / "sub").mkdir()
    (tmp / "sub" / "deep.py").write_text("x=1\n")

    # 1. Deteksi Python + entry point
    assert detect_project_type(tmp) == "Python", detect_project_type(tmp)
    assert get_entry_points(tmp) == ["main.py"]
    assert detect_project_type(tempfile.mkdtemp()) == "Generic"

    # 2. Tree skip yang harus di-skip, tampilkan yang relevan
    tree = build_file_tree(tmp)
    for bad in ("PLAN.md", "soul.md", ".env", ".venv", "__pycache__", "plan", ".pyc"):
        assert bad not in tree, (bad, tree)
    for good in ("main.py", "README.md", "requirements.txt", "sub/", "deep.py"):
        assert good in tree, (good, tree)

    # 3. Key files: baca yang perlu, potong yang panjang
    keys = get_key_files(tmp)
    assert set(keys) == {"README.md", "requirements.txt"}, set(keys)

    # 4. Bukan git repo → fallback sopan
    assert get_git_summary(tmp) == {"is_repo": False}

    # 5. scan_project lengkap + format sesuai spec
    ctx = scan_project(tmp)
    for needle in ("Project: ", "Type: Python", "Entry point: main.py",
                   "textual, litellm", "Structure:", "Git: bukan git repo",
                   "README: # Demo"):
        assert needle in ctx, (needle, ctx[:300])
    assert "SECRET" not in ctx and "planning" not in ctx

    # 6. Folder hilang / aneh → tidak crash
    assert "tidak ditemukan" in build_file_tree(tmp / "nope")
    assert scan_project(tmp / "nope").startswith("Project: nope")
    assert "scan gagal" not in scan_project(tmp / "nope")

    # 7. Repo asli multacd ke-scan beneran
    real = Path(__file__).resolve().parent.parent
    ctx = scan_project(real)
    assert "Type: Python" in ctx and "agent_loop.py" in ctx, ctx[:500]
    assert "soul.md" not in ctx.split("Structure:")[1].split("Git:")[0]

    print("✅ codebase self-test OK (7 skenario)")
