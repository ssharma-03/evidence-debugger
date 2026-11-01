"""Banned-fix detection on diffs vs init baseline."""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .snapshot import current_map, snapshot_map

RULES = [
    {"id": "py-swallow", "severity": "BLOCK", "pattern": r"except(\s+Exception)?\s*:", "description": "bare except or except Exception with only pass/continue/return None"},
    {"id": "js-empty-catch", "severity": "BLOCK", "pattern": r"catch\s*\([^)]*\)\s*\{\s*\}|\.catch\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)", "description": "empty catch or empty .catch(() => {})"},
    {"id": "test-skip", "severity": "BLOCK", "pattern": r"@pytest\.mark\.skip|pytest\.mark\.xfail|pytest\.skip\(|unittest\.skip|it\.skip|test\.skip|xit\(|xdescribe\(|t\.Skip\(|@Ignore|@Disabled", "description": "skipped or disabled test"},
    {"id": "suppress-types", "severity": "BLOCK", "pattern": r"# type: ignore|# noqa|// @ts-ignore|// @ts-nocheck|eslint-disable", "description": "type or linter suppression"},
    {"id": "test-deleted", "severity": "BLOCK", "pattern": "", "description": "a test file was removed"},
    {"id": "assertion-weakened", "severity": "BLOCK", "pattern": "", "description": "assertion line removed without equivalent replacement"},
    {"id": "expected-value-edited", "severity": "BLOCK", "pattern": "", "description": "test assertion literals edited to match actuals"},
    {"id": "assert-true", "severity": "BLOCK", "pattern": r"assert\s+True\b|expect\(\s*true\s*\)\.toBe\(\s*true\s*\)", "description": "assert True / expect(true).toBe(true)"},
    {"id": "sleep-added", "severity": "WARN", "pattern": r"time\.sleep\(|setTimeout\(|Thread\.sleep\(", "description": "sleep added"},
    {"id": "retry-added", "severity": "WARN", "pattern": r"\bretries\b|\bretry\b|\bbackoff\b", "description": "retry/backoff added"},
    {"id": "dependency-pinned", "severity": "WARN", "pattern": "", "description": "dependency pin or downgrade in lock/manifest"},
    {"id": "hardcoded-literal", "severity": "WARN", "pattern": "", "description": "new return of a literal that matched a removed assertion literal"},
]

RULE_BY_ID = {r["id"]: r for r in RULES}

_TEST_FILE = re.compile(
    r"(?:^|/)(?:test_[^/]+\.py|[^/]+_test\.py|[^/]+\.test\.[jt]sx?|[^/]+\.spec\.[jt]sx?|tests?\.py)$",
    re.I,
)
_ASSERT_LINE = re.compile(
    r"(?i)\b(assert|expect\(|should\.|self\.assert|self\.expect|require\()\b"
)
_STR_LIT = re.compile(r"""(['"])(?:\\.|(?!\1).)*\1""")
_NUM_LIT = re.compile(r"\b\d+(?:\.\d+)?\b")
_PY_EXCEPT = re.compile(r"^(\s*)except(\s+Exception)?\s*:\s*(.*)$")
_PIN_FILES = ("requirements.txt", "requirements-dev.txt", "package.json", "pyproject.toml", "go.mod")


class Finding(object):
    def __init__(self, rule_id, severity, path, detail, evidence=""):
        self.rule_id = rule_id
        self.severity = severity
        self.path = path
        self.detail = detail
        self.evidence = evidence

    def as_dict(self):
        return {
            "rule": self.rule_id,
            "severity": self.severity,
            "path": self.path,
            "detail": self.detail,
            "evidence": self.evidence,
        }


def is_test_path(rel: str) -> bool:
    """True if relative path looks like a test file."""
    posix = rel.replace("\\", "/")
    if "/tests/" in "/" + posix or posix.startswith("tests/"):
        if posix.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java")):
            return True
    return bool(_TEST_FILE.search(posix))


def _strip_lits(line: str) -> str:
    s = _STR_LIT.sub("STR", line)
    s = _NUM_LIT.sub("NUM", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_unified_hunks(diff_text: str) -> Dict[str, Dict[str, List[str]]]:
    """Map path -> {added, removed} lines (without +/- prefix)."""
    files = {}  # type: Dict[str, Dict[str, List[str]]]
    current = None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            if path == "/dev/null":
                current = None
                continue
            current = path
            files.setdefault(current, {"added": [], "removed": []})
            continue
        if line.startswith("--- "):
            path = line[4:].strip()
            if path.startswith("a/"):
                path = path[2:]
            if path != "/dev/null":
                files.setdefault(path, {"added": [], "removed": []})
            continue
        if current is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            files[current]["added"].append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            files[current]["removed"].append(line[1:])
    return files


def git_unidiff(root: Path, base_ref: str) -> str:
    proc = subprocess.run(
        ["git", "diff", "-U0", base_ref],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    text = proc.stdout.decode("utf-8", errors="replace") if proc.returncode == 0 else ""
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    extra = []
    if untracked.returncode == 0:
        for rel in untracked.stdout.decode("utf-8", errors="replace").splitlines():
            rel = rel.strip()
            if not rel:
                continue
            p = root / rel
            try:
                body = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            extra.append("--- /dev/null")
            extra.append("+++ b/%s" % rel.replace("\\", "/"))
            for ln in body.splitlines():
                extra.append("+" + ln)
    return text + ("\n" + "\n".join(extra) if extra else "")


def snapshot_unidiff(root: Path, snap_root: Path) -> Tuple[str, List[str]]:
    old = snapshot_map(snap_root)
    new, skipped = current_map(root)
    import difflib

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


def _py_swallow_in_added(added: List[str]) -> Optional[str]:
    i = 0
    while i < len(added):
        m = _PY_EXCEPT.match(added[i])
        if not m:
            i += 1
            continue
        indent = m.group(1)
        rest = (m.group(3) or "").strip()
        if rest in ("pass", "continue", "return None", "returnNone"):
            return added[i]
        # following body at greater indent, only those tokens
        j = i + 1
        body = []
        while j < len(added):
            ln = added[j]
            if not ln.strip():
                j += 1
                continue
            # if same or less indent, body ended
            cur_indent = ln[: len(ln) - len(ln.lstrip(" \t"))]
            if len(cur_indent) <= len(indent) and ln.lstrip()[:6] not in ():
                if not ln.startswith(indent + " ") and not ln.startswith(indent + "\t"):
                    break
            body.append(ln.strip())
            j += 1
        if body and all(b in ("pass", "continue", "return None") for b in body):
            return added[i]
        if not body and not rest:
            # except: with no body in hunk still suspicious if next would be pass elsewhere
            pass
        i += 1
    return None


def _literals(line: str) -> List[str]:
    found = [m.group(0) for m in _STR_LIT.finditer(line)]
    found.extend(m.group(0) for m in _NUM_LIT.finditer(line))
    return found


def analyze_hunks(hunks: Dict[str, Dict[str, List[str]]], deleted_paths: Optional[List[str]] = None) -> List[Finding]:
    """Run all rules on parsed hunks."""
    findings = []  # type: List[Finding]
    deleted_paths = deleted_paths or []
    for rel in deleted_paths:
        if is_test_path(rel):
            findings.append(Finding("test-deleted", "BLOCK", rel, "test file removed"))

    pin_names = set(_PIN_FILES)
    for path, ch in hunks.items():
        posix = path.replace("\\", "/")
        added = ch.get("added") or []
        removed = ch.get("removed") or []
        added_text = "\n".join(added)
        if posix == "/dev/null":
            continue

        if _PY_EXCEPT.search("\n".join(added)) or any(_PY_EXCEPT.match(x) for x in added):
            hit = _py_swallow_in_added(added)
            if hit is not None:
                findings.append(Finding("py-swallow", "BLOCK", posix, "empty/swallowing except", hit))

        for rid, pat in (
            ("js-empty-catch", RULE_BY_ID["js-empty-catch"]["pattern"]),
            ("test-skip", RULE_BY_ID["test-skip"]["pattern"]),
            ("suppress-types", RULE_BY_ID["suppress-types"]["pattern"]),
            ("assert-true", RULE_BY_ID["assert-true"]["pattern"]),
            ("sleep-added", RULE_BY_ID["sleep-added"]["pattern"]),
            ("retry-added", RULE_BY_ID["retry-added"]["pattern"]),
        ):
            rg = re.compile(pat)
            for ln in added:
                if rg.search(ln):
                    findings.append(Finding(rid, RULE_BY_ID[rid]["severity"], posix, RULE_BY_ID[rid]["description"], ln.strip()))

        if Path(posix).name in pin_names or posix.endswith("requirements.txt"):
            if added and (removed or any(x.strip() for x in added)):
                findings.append(Finding("dependency-pinned", "WARN", posix, "manifest changed", ""))

        if is_test_path(posix):
            rem_assert = [ln for ln in removed if _ASSERT_LINE.search(ln)]
            add_assert = [ln for ln in added if _ASSERT_LINE.search(ln)]
            if rem_assert and not add_assert:
                findings.append(Finding("assertion-weakened", "BLOCK", posix, "assertion removed", rem_assert[0].strip()))
            # expected-value-edited: same shape after stripping literals
            for rln in rem_assert:
                rnorm = _strip_lits(rln)
                for aln in add_assert:
                    anorm = _strip_lits(aln)
                    if rnorm == anorm and rln.strip() != aln.strip():
                        findings.append(
                            Finding(
                                "expected-value-edited",
                                "BLOCK",
                                posix,
                                "assertion literals changed",
                                aln.strip(),
                            )
                        )

            rem_lits = []
            for ln in rem_assert:
                rem_lits.extend(_literals(ln))
            for ln in added:
                m = re.search(r"\breturn\s+(.+)$", ln.strip())
                if m:
                    val = m.group(1).strip().rstrip(";")
                    for lit in rem_lits:
                        if val == lit or val.strip("'\"") == lit.strip("'\""):
                            findings.append(Finding("hardcoded-literal", "WARN", posix, "returned removed assertion literal", ln.strip()))

    return findings


def diff_stat_and_hash(hunks: Dict[str, Dict[str, List[str]]]) -> Tuple[List[str], str, str]:
    """Return changed files, short stat, and hash of the change set."""
    files = sorted(hunks.keys())
    added_n = sum(len(hunks[f].get("added") or []) for f in files)
    removed_n = sum(len(hunks[f].get("removed") or []) for f in files)
    stat = "%d files, +%d -%d" % (len(files), added_n, removed_n)
    payload_parts = []
    for f in files:
        payload_parts.append(f)
        for ln in hunks[f].get("removed") or []:
            payload_parts.append("-" + ln)
        for ln in hunks[f].get("added") or []:
            payload_parts.append("+" + ln)
    digest = hashlib.sha256("\n".join(payload_parts).encode("utf-8", errors="replace")).hexdigest()
    return files, stat, digest


def git_deleted_files(root: Path, base_ref: str) -> List[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-status", "--diff-filter=D", base_ref],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    out = []
    if proc.returncode != 0:
        return out
    for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            out.append(parts[1].strip())
    return out
