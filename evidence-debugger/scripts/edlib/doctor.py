"""Environment and skill-integrity checks."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from . import __version__
from .envinfo import collect, format_envinfo
from .paths import debug_dir

ALLOWLIST_TOP = {"SKILL.md", "LICENSE", "SHA256SUMS"}
ALLOWLIST_EXTRA = {".installed-by.json"}


def skill_dir_from_ed() -> Path:
    """evidence-debugger/ folder containing SKILL.md (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent.parent


def parse_sha256sums(text: str) -> Dict[str, str]:
    """Map relative posix path -> hex digest."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, rel = parts
        out[rel.replace("\\", "/")] = digest.lower()
    return out


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(str(path), "rb") as fp:
        while True:
            chunk = fp.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def list_allowlisted_files(skill: Path) -> List[str]:
    """Relative posix paths the installer may copy."""
    files = []
    for name in ("SKILL.md", "LICENSE", "SHA256SUMS"):
        p = skill / name
        if p.is_file():
            files.append(name)
    scripts = skill / "scripts"
    if scripts.is_dir():
        for p in sorted(scripts.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            files.append(p.relative_to(skill).as_posix())
    refs = skill / "references"
    if refs.is_dir():
        for p in sorted(refs.glob("*.md")):
            files.append(p.relative_to(skill).as_posix())
    return files


def unknown_skill_files(skill: Path) -> List[str]:
    """Files under skill dir that are not on the installer allowlist."""
    unknown = []
    skill = skill.resolve()
    for p in skill.rglob("*"):
        if not p.is_file():
            continue
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        rel = p.relative_to(skill).as_posix()
        if rel in ALLOWLIST_EXTRA:
            continue
        top = rel.split("/", 1)[0]
        if rel in ("SKILL.md", "LICENSE", "SHA256SUMS"):
            continue
        if rel.startswith("scripts/") and rel.endswith(".py"):
            continue
        if rel.startswith("references/") and rel.endswith(".md"):
            continue
        unknown.append(rel)
        _ = top
    return sorted(unknown)


def verify_checksums(skill: Path) -> Tuple[bool, List[str]]:
    sums_path = skill / "SHA256SUMS"
    problems = []
    if not sums_path.is_file():
        return False, ["SHA256SUMS missing"]
    expected = parse_sha256sums(sums_path.read_text(encoding="utf-8", errors="replace"))
    listed = set(expected)
    actual = set(list_allowlisted_files(skill))
    for rel in sorted(listed - actual):
        problems.append("checksum lists missing file: %s" % rel)
    for rel in sorted(actual - listed):
        if rel == "SHA256SUMS":
            continue
        problems.append("file not in SHA256SUMS: %s" % rel)
    for rel, digest in sorted(expected.items()):
        path = skill / rel
        if not path.is_file():
            continue
        got = file_sha256(path)
        if got != digest:
            problems.append("checksum mismatch: %s" % rel)
    return (not problems), problems


def can_write(root: Path) -> Tuple[bool, str]:
    probe = debug_dir(root) / ".doctor-write"
    try:
        debug_dir(root).mkdir(parents=True, exist_ok=True)
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
        return True, ""
    except OSError as exc:
        return False, "%s (%s)" % (probe, exc)


def git_available() -> str:
    from .paths import git_toplevel

    try:
        top = git_toplevel(Path.cwd())
    except Exception:
        top = None
    if top:
        return "yes (%s)" % top
    # git binary?
    import shutil

    if shutil.which("git"):
        return "git present, not a repository"
    return "git not found"


def run_doctor(root: Path, json_mode: bool = False) -> Tuple[int, Dict[str, object], str]:
    """Return (exit_code, payload, human_text). Exit 6 on any problem."""
    from . import EXIT_ENV, EXIT_OK

    problems = []  # type: List[str]
    py = "%s.%s.%s" % sys.version_info[:3]
    if sys.version_info < (3, 8):
        problems.append("Python %s is older than 3.8" % py)
    write_ok, write_err = can_write(root)
    if not write_ok:
        problems.append("cannot write to root: %s" % write_err)
    skill = skill_dir_from_ed()
    ck_ok, ck_problems = verify_checksums(skill)
    problems.extend(ck_problems)
    extra = unknown_skill_files(skill)
    if extra:
        problems.append("unknown files in skill folder: %s" % ", ".join(extra))
    env = collect(root)
    payload = {
        "ok": not problems,
        "version": __version__,
        "python_version": py,
        "write_ok": write_ok,
        "git": git_available(),
        "checksums_ok": ck_ok,
        "unknown_files": extra,
        "interpreter": sys.executable,
        "skill_dir": str(skill),
        "problems": problems,
        "envinfo": env,
    }
    lines = [
        "evidence-debugger doctor %s" % __version__,
        "python         : %s" % py,
        "interpreter    : %s" % sys.executable,
        "write to root  : %s" % ("ok" if write_ok else "FAIL"),
        "git            : %s" % payload["git"],
        "checksums      : %s" % ("ok" if ck_ok else "FAIL"),
        "unknown files  : %s" % (extra if extra else "(none)"),
        "",
        format_envinfo(env).rstrip(),
    ]
    if problems:
        lines.append("")
        lines.append("problems:")
        for p in problems:
            lines.append("  - %s" % p)
    text = "\n".join(lines) + "\n"
    code = EXIT_OK if not problems else EXIT_ENV
    _ = json_mode
    return code, payload, text
