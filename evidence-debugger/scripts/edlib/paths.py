"""Project root detection and path confinement."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional


class PathError(ValueError):
    """Invalid or escaped path."""


def git_toplevel(cwd: Path) -> Optional[Path]:
    """Return git work tree root for cwd, or None if git is missing or cwd is not a repo."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    text = proc.stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    return Path(text).resolve()


def resolve_root(explicit: Optional[str] = None, cwd: Optional[Path] = None) -> Path:
    """Resolve project root: --root, else git toplevel, else cwd."""
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not root.is_dir():
            raise PathError("root is not a directory: %s" % root)
        return root
    here = Path(cwd) if cwd is not None else Path.cwd()
    here = here.resolve()
    git_root = git_toplevel(here)
    if git_root is not None:
        return git_root
    return here


def is_under(path: Path, root: Path) -> bool:
    """True if path is root or a descendant of root."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def debug_dir(root: Path) -> Path:
    """Return <root>/.debug."""
    return root / ".debug"


def _parts_has_git(rel: Path) -> bool:
    return ".git" in rel.parts


def confine(path: Path, root: Path, *, allow_debug: bool = False, allow_git: bool = False) -> Path:
    """Resolve path and require it stay inside root.

    Rejects .. escapes and symlinks that resolve outside root.
    Rejects .git/ unless allow_git. Rejects .debug/ unless allow_debug.
    """
    root_r = root.resolve()
    raw = Path(path)
    resolved = (root_r / raw).resolve() if not raw.is_absolute() else raw.resolve()
    if not is_under(resolved, root_r):
        raise PathError("path escapes project root: %s" % path)
    try:
        rel = resolved.relative_to(root_r)
    except ValueError:
        raise PathError("path escapes project root: %s" % path)
    if not allow_git and _parts_has_git(rel):
        raise PathError("refusing to touch .git/: %s" % path)
    if not allow_debug and rel.parts and rel.parts[0] == ".debug":
        raise PathError("refusing user path under .debug/: %s" % path)
    return resolved


def relative_to_root(path: Path, root: Path) -> str:
    """POSIX-style relative path string for storage."""
    rel = confine(path, root, allow_debug=True, allow_git=False)
    return rel.relative_to(root.resolve()).as_posix()
