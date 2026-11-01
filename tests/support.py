"""Test helpers: put evidence-debugger/scripts on sys.path."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "evidence-debugger" / "scripts"
ED = SCRIPTS / "ed.py"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def tmp_dir():
    return tempfile.TemporaryDirectory()


def write(path: Path, text: str, newline="\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\n", newline)
    path.write_bytes(data.encode("utf-8"))


def git_init(path: Path):
    import subprocess

    subprocess.run(["git", "init"], cwd=str(path), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "ed@example.com"], cwd=str(path), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "ed"], cwd=str(path), check=True, stdout=subprocess.DEVNULL)


def git_commit_all(path: Path, msg="init"):
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=str(path), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "commit", "-m", msg], cwd=str(path), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_ed(root: Path, extra, json_mode=False, env=None):
    import subprocess

    cmd = [sys.executable, str(ED), "--root", str(root)]
    if json_mode:
        cmd.append("--json")
    cmd.extend(extra)
    envp = os.environ.copy()
    envp.pop("ED_DEBUG", None)
    if env:
        envp.update(env)
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(root),
        env=envp,
    )
    return proc.returncode, proc.stdout.decode("utf-8", errors="replace"), proc.stderr.decode("utf-8", errors="replace")
