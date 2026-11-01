"""Non-git baseline snapshot of text files under the project root."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Tuple

SKIP_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    "target",
    "__pycache__",
    ".debug",
    ".git",
    ".debug.old",
}

BINARY_EXT = {
    ".pyc",
    ".pyo",
    ".so",
    ".dll",
    ".exe",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".zip",
    ".gz",
    ".tgz",
    ".whl",
    ".bin",
    ".class",
    ".o",
    ".a",
    ".woff",
    ".woff2",
}

MAX_FILES = 500
MAX_FILE_BYTES = 256 * 1024


def is_probably_binary(path: Path) -> bool:
    """True if file looks binary."""
    if path.suffix.lower() in BINARY_EXT:
        return True
    try:
        with open(str(path), "rb") as fp:
            chunk = fp.read(8192)
        if b"\0" in chunk:
            return True
    except OSError:
        return True
    return False


def iter_text_files(root: Path):
    """Yield text files under root, skipping denylisted directories."""
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".debug.old")]
        rel_dir = Path(dirpath)
        try:
            rel_dir.relative_to(root)
        except ValueError:
            continue
        for name in filenames:
            p = Path(dirpath) / name
            yield p


def take_snapshot(root: Path, dest: Path) -> Dict[str, object]:
    """Copy text files into dest. Returns stats including skipped paths."""
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    skipped = []  # type: List[str]
    for path in iter_text_files(root):
        try:
            rel = path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        if copied >= MAX_FILES:
            skipped.append(rel.as_posix())
            continue
        try:
            size = path.stat().st_size
        except OSError:
            skipped.append(rel.as_posix())
            continue
        if size > MAX_FILE_BYTES or is_probably_binary(path):
            skipped.append(rel.as_posix())
            continue
        target = dest / rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            data = path.read_bytes()
            target.write_bytes(data)
            copied += 1
        except OSError:
            skipped.append(rel.as_posix())
    return {"copied": copied, "skipped": skipped, "partial": len(skipped) > 0}


def snapshot_map(snap_root: Path) -> Dict[str, str]:
    """Map posix relative path -> text for files in a snapshot."""
    out = {}  # type: Dict[str, str]
    if not snap_root.exists():
        return out
    for path in snap_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(snap_root).as_posix()
        try:
            out[rel] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return out


def current_map(root: Path) -> Tuple[Dict[str, str], List[str]]:
    """Current text files plus skipped paths (limits)."""
    out = {}  # type: Dict[str, str]
    skipped = []  # type: List[str]
    n = 0
    for path in iter_text_files(root):
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        if n >= MAX_FILES:
            skipped.append(rel)
            continue
        try:
            size = path.stat().st_size
        except OSError:
            skipped.append(rel)
            continue
        if size > MAX_FILE_BYTES or is_probably_binary(path):
            skipped.append(rel)
            continue
        try:
            out[rel] = path.read_text(encoding="utf-8", errors="replace")
            n += 1
        except OSError:
            skipped.append(rel)
    return out, skipped


def snapshot_unidiff(root: Path, snap_root: Path) -> Tuple[str, List[str]]:
    """Return unified diff of files modified/added/removed vs snapshot, and skipped paths."""
    import difflib

    old = snapshot_map(snap_root)
    new, skipped = current_map(root)

    chunks = []
    all_keys = sorted(set(old) | set(new))
    for key in all_keys:
        a = old.get(key, "")
        b = new.get(key, "")
        if a == b:
            continue
        a_lines = a.splitlines()
        b_lines = b.splitlines()
        diff = difflib.unified_diff(a_lines, b_lines, fromfile="a/" + key, tofile="b/" + key, n=0)
        chunks.append("\n".join(diff))
    return "\n".join(chunks), skipped

