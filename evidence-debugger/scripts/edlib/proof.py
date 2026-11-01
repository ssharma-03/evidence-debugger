"""Proof gate: seven checks the agent cannot skip."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import markers as markers_mod
from .guard import Finding


def check_baseline_exists(baseline) -> Tuple[bool, str]:
    if not baseline:
        return False, "baseline exists"
    return True, "baseline exists"


def check_latest_baseline_pass(runs, baseline_cmd, changed_files, root: Path) -> Tuple[bool, str]:
    """Latest run of the baseline command exited 0 and is newer than changed files."""
    name = "latest baseline run passed and is newer than edits"
    if not baseline_cmd:
        return False, name
    matching = [r for r in runs if r.get("argv") == baseline_cmd]
    if not matching:
        return False, name
    latest = matching[-1]
    if latest.get("timed_out") or int(latest.get("exit_code", 1)) != 0:
        return False, name
    run_path = latest.get("log") or ""
    run_mtime = latest.get("mtime")
    if run_mtime is None:
        lp = Path(run_path) if run_path else None
        if lp and Path(lp).exists():
            run_mtime = Path(lp).stat().st_mtime
        else:
            # fall back to now-ish from ts not available: fail closed if we have changed files
            run_mtime = 0
    latest_edit = 0.0
    for rel in changed_files:
        p = root / rel
        try:
            if p.exists():
                mt = p.stat().st_mtime
                if mt > latest_edit:
                    latest_edit = mt
        except OSError:
            continue
    if changed_files and latest_edit and run_mtime < latest_edit:
        return False, name
    return True, name


def check_also_commands(also_results: List[Dict[str, Any]]) -> Tuple[bool, str]:
    name = "--also commands exited 0"
    if not also_results:
        return True, name
    for r in also_results:
        if r.get("timed_out") or int(r.get("exit_code", 1)) != 0:
            return False, name
    return True, name


def check_no_markers(root: Path) -> Tuple[bool, str]:
    leftover = markers_mod.list_markers_in_tree(root)
    name = "no markers remain"
    if leftover:
        return False, name
    return True, name


def check_guard_clean(findings: List[Finding], approvals: set) -> Tuple[bool, str]:
    name = "guard has no unapproved BLOCK finding"
    for f in findings:
        if f.severity == "BLOCK" and f.rule_id not in approvals:
            return False, name
    return True, name


def check_hypothesis_survived(hypos: List[Dict[str, Any]]) -> Tuple[bool, str]:
    name = "at least one hypothesis survived with evidence"
    for h in hypos:
        if h.get("status") == "survived" and len(str(h.get("evidence") or "")) >= 20:
            return True, name
    return False, name


def check_cause(cause: str, change_texts: List[str]) -> Tuple[bool, str]:
    name = "--cause is specific and not a copy of --change"
    if cause is None or len(cause.strip()) < 30:
        return False, name
    c = cause.strip()
    for ch in change_texts:
        if ch and c == ch.strip():
            return False, name
    return True, name


def evaluate(
    baseline,
    runs,
    baseline_cmd,
    changed_files,
    root,
    also_results,
    findings,
    approvals,
    hypos,
    cause,
    change_texts,
) -> Tuple[bool, List[Dict[str, str]]]:
    """Run all seven checks. Returns (ok, list of {name, result})."""
    checks = [
        check_baseline_exists(baseline),
        check_latest_baseline_pass(runs, baseline_cmd, changed_files, root),
        check_also_commands(also_results),
        check_no_markers(root),
        check_guard_clean(findings, approvals),
        check_hypothesis_survived(hypos),
        check_cause(cause, change_texts),
    ]
    rows = []
    ok = True
    for passed, name in checks:
        rows.append({"name": name, "result": "PASS" if passed else "FAIL"})
        if not passed:
            ok = False
    return ok, rows


def failed_names(rows: List[Dict[str, str]]) -> str:
    fails = [r["name"] for r in rows if r["result"] == "FAIL"]
    return ", ".join(fails)
