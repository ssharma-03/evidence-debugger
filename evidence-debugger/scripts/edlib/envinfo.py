"""Environment snapshot used at init and by doctor."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


def _run(argv, timeout=8):
    try:
        proc = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.decode("utf-8", errors="replace").strip()


def _which_all(names):
    found = {}  # type: Dict[str, str]
    if os.name == "nt":
        for name in names:
            out = _run(["where", name])
            if out:
                found[name] = out.replace("\r\n", "\n")
    else:
        for name in names:
            out = _run(["which", "-a", name])
            if not out:
                p = shutil.which(name)
                out = p or ""
            if out:
                found[name] = out
    return found


def _node_version():
    return _run(["node", "--version"])


def collect(root: Path) -> Dict[str, object]:
    """OS, Python, Node, interpreters, venv, git, cwd."""
    git_root = _run(["git", "rev-parse", "--show-toplevel"], timeout=10)
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=10)
    commit = _run(["git", "rev-parse", "HEAD"], timeout=10)
    venv = sys.prefix if getattr(sys, "base_prefix", sys.prefix) != sys.prefix else os.environ.get("VIRTUAL_ENV", "")
    info = {
        "os": os.name,
        "platform": sys.platform,
        "python_version": "%s.%s.%s" % sys.version_info[:3],
        "python_executable": sys.executable,
        "node_version": _node_version() or "",
        "which": _which_all(["python", "python3", "node"]),
        "virtualenv": venv or "",
        "git_root": git_root,
        "git_branch": branch,
        "git_commit": commit,
        "cwd": str(Path.cwd()),
        "project_root": str(root.resolve()),
    }
    return info


def format_envinfo(info: Dict[str, object]) -> str:
    """Human ASCII dump."""
    lines = [
        "os            : %s (%s)" % (info.get("os"), info.get("platform")),
        "python        : %s (%s)" % (info.get("python_version"), info.get("python_executable")),
        "node          : %s" % (info.get("node_version") or "(not found)"),
        "virtualenv    : %s" % (info.get("virtualenv") or "(none)"),
        "git branch    : %s" % (info.get("git_branch") or "(n/a)"),
        "git commit    : %s" % (info.get("git_commit") or "(n/a)"),
        "cwd           : %s" % info.get("cwd"),
        "project root  : %s" % info.get("project_root"),
    ]
    which = info.get("which") or {}
    if isinstance(which, dict):
        for k in sorted(which):
            val = str(which[k]).replace("\n", " | ")
            lines.append("which %-8s: %s" % (k, val))
    return "\n".join(lines) + "\n"
