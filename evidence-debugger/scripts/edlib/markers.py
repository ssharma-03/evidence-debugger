"""Insert, list, check, and remove debug marker lines."""

from __future__ import annotations

import hashlib
import os
import py_compile
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .paths import PathError, confine

TOKEN_RE = re.compile(r"EDBG_[0-9a-fA-F]{8}")

EXT_LANG = {
    ".py": "py",
    ".js": "js",
    ".mjs": "js",
    ".cjs": "js",
    ".ts": "js",
    ".tsx": "js",
    ".jsx": "js",
    ".go": "go",
    ".rs": "rs",
    ".java": "java",
    ".kt": "java",
    ".rb": "rb",
    ".php": "php",
    ".sh": "sh",
    ".bash": "sh",
}

_CONT_END = re.compile(
    r"(,|\(|\[|\{|\\|\+|-|\*|/|%|&|\||\^|=|<<|>>|\+=|-=|\*=|/=|//=|%=|@)$"
)

MAX_BYTES = 2 * 1024 * 1024


class MarkerError(ValueError):
    """Marker operation refused."""


def new_token() -> str:
    """Return EDBG_ plus 8 hex chars."""
    raw = hashlib.sha256(("%s-%s" % (time.time(), os.urandom(8))).encode("utf-8")).hexdigest()
    return "EDBG_" + raw[:8]


def marker_source(lang: str, token: str) -> str:
    """Unindented marker statement for a language."""
    if lang == "py":
        return '__import__("sys").stderr.write("%s\\n")' % token
    if lang == "js":
        return 'console.error("%s");' % token
    if lang == "go":
        return 'println("%s")' % token
    if lang == "rs":
        return 'eprintln!("%s");' % token
    if lang == "java":
        return 'System.err.println("%s");' % token
    if lang == "rb":
        return 'warn "%s"' % token
    if lang == "php":
        return 'error_log("%s");' % token
    if lang == "sh":
        return "echo %s >&2" % token
    raise MarkerError("unsupported language")


def _detect_newline(data: bytes) -> str:
    if b"\r\n" in data:
        return "\r\n"
    return "\n"


def _split_keep(text: str, nl: str) -> Tuple[List[str], bool]:
    trailing = text.endswith(nl) if nl else text.endswith("\n")
    if nl == "\r\n":
        parts = text.split("\r\n")
    else:
        parts = text.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
        trailing = True
    return parts, trailing


def _join_lines(lines: List[str], nl: str, trailing: bool) -> str:
    body = nl.join(lines)
    if trailing:
        body += nl
    return body


def _indent_of(line: str) -> str:
    i = 0
    while i < len(line) and line[i] in " \t":
        i += 1
    return line[:i]


_PY_CONT_OPS = (
    ",",
    "(",
    "[",
    "{",
    "\\",
    "+",
    "-",
    "*",
    "/",
    "%",
    "&",
    "|",
    "^",
    "=",
    "@",
    "and",
    "or",
)


def python_continuation_line(prev: str) -> bool:
    """True if previous non-blank Python line looks like a continuation."""
    s = prev.rstrip()
    if not s:
        return False
    stripped = s.strip()
    if stripped.endswith(":") and not stripped.endswith(","):
        return False
    if s.endswith("\\"):
        return True
    if stripped.endswith(_PY_CONT_OPS[:15]):
        # ends with punctuation operator
        pass
    core = stripped
    if core.endswith((",", "(", "[", "{", "\\")):
        return True
    for op in ("+", "-", "*", "/", "%", "&", "|", "^", "=", "@", "<<", ">>"):
        if core.endswith(op) and not core.endswith("=="):
            # '=' at end of assignment to name is not continuation of next as expr of previous...
            # actually `x =` is continuation.
            if op == "=" and core.endswith("="):
                return True
            if op != "=":
                return True
    if re.search(r"(\band|\bor)\s*$", core):
        return True
    return False


def _backup(root: Path, rel: Path, data: bytes) -> Path:
    dest_dir = root / ".debug" / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = str(int(time.time() * 1000))
    name = rel.as_posix().replace("/", "__") + "." + stamp
    dest = dest_dir / name
    dest.write_bytes(data)
    if os.name == "posix":
        try:
            os.chmod(str(dest), 0o600)
        except OSError:
            pass
    return dest


def add_marker(root: Path, rel: str, line_no: int, token: Optional[str] = None) -> Dict[str, str]:
    """Insert a marker before 1-based line_no. Returns token and path info."""
    path = confine(Path(rel), root, allow_debug=False, allow_git=False)
    if not path.is_file():
        raise MarkerError("file not found: %s" % rel)
    ext = path.suffix.lower()
    lang = EXT_LANG.get(ext)
    if not lang:
        raise MarkerError(
            "unsupported extension %s; place a token manually then run marker register --token T --file F"
            % ext
        )
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise MarkerError(str(exc))
    if size > MAX_BYTES:
        raise MarkerError("file too large (>%s bytes)" % MAX_BYTES)
    raw = path.read_bytes()
    if b"\0" in raw[:8192]:
        raise MarkerError("refusing binary file")
    text = raw.decode("utf-8", errors="replace")
    nl = _detect_newline(raw)
    lines, trailing = _split_keep(text, nl)
    n = line_no
    if n < 1 or n > len(lines) + 1:
        raise MarkerError("line out of range")
    if lang == "py":
        prev = None
        for i in range(n - 2, -1, -1):
            if lines[i].strip():
                prev = lines[i]
                break
        if prev is not None and python_continuation_line(prev):
            raise MarkerError("refusing insert: previous line looks like a Python continuation")
    token = token or new_token()
    indent = ""
    if n <= len(lines) and n >= 1:
        target = lines[n - 1] if n - 1 < len(lines) else ""
        indent = _indent_of(target)
    marker_line = indent + marker_source(lang, token)
    new_lines = lines[: n - 1] + [marker_line] + lines[n - 1 :]
    new_text = _join_lines(new_lines, nl, trailing or True)
    new_bytes = new_text.encode("utf-8")
    rel_path = path.relative_to(root.resolve())
    _backup(root, rel_path, raw)
    path.write_bytes(new_bytes)
    if lang == "py":
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception:
            path.write_bytes(raw)
            raise MarkerError("py_compile failed; original bytes restored")
    return {
        "token": token,
        "file": rel_path.as_posix(),
        "line": str(n),
        "text": marker_line,
    }


def generated_line_core(lang: str, token: str) -> str:
    return marker_source(lang, token)


def list_markers_in_tree(root: Path) -> List[Dict[str, str]]:
    """Scan project files (not .git/.debug) for EDBG_ tokens."""
    found = []  # type: List[Dict[str, str]]
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in (".git", ".debug") and not d.startswith(".debug.old")]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                if p.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue
            try:
                data = p.read_bytes()
            except OSError:
                continue
            if b"\0" in data[:8192]:
                continue
            text = data.decode("utf-8", errors="replace")
            rel = p.relative_to(root).as_posix()
            for i, line in enumerate(text.splitlines(), 1):
                m = TOKEN_RE.search(line)
                if m:
                    found.append(
                        {
                            "token": m.group(0),
                            "file": rel,
                            "line": str(i),
                            "text": line,
                        }
                    )
    return found


def check_log(log_text: str, markers: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Return each marker with reached true/false."""
    out = []
    blob = log_text or ""
    for m in markers:
        tok = m["token"]
        reached = tok in blob
        row = dict(m)
        row["reached"] = "yes" if reached else "no"
        out.append(row)
    return out


def remove_all(root: Path, records: List[Dict[str, str]]) -> List[str]:
    """Remove lines that exactly equal generated marker lines after stripping indent.

    If a recorded marker line was modified by hand, refuse.
    """
    errors = []
    by_file = {}  # type: Dict[str, List[Dict[str, str]]]
    for rec in records:
        by_file.setdefault(rec["file"], []).append(rec)
    for rel, recs in by_file.items():
        path = confine(Path(rel), root, allow_debug=False, allow_git=False)
        if not path.is_file():
            errors.append("missing file %s" % rel)
            continue
        raw = path.read_bytes()
        nl = _detect_newline(raw)
        text = raw.decode("utf-8", errors="replace")
        lines, trailing = _split_keep(text, nl)
        ext = path.suffix.lower()
        lang = EXT_LANG.get(ext)
        new_lines = []
        used = set()
        for line in lines:
            stripped = line.lstrip(" \t")
            matched_rec = None
            for rec in recs:
                if rec["token"] in line:
                    matched_rec = rec
                    break
            if matched_rec is None:
                new_lines.append(line)
                continue
            token = matched_rec["token"]
            expected = None
            if lang:
                expected = marker_source(lang, token)
            rec_text = (matched_rec.get("text") or "").lstrip(" \t")
            core = stripped.rstrip("\r\n")
            if expected is not None and core != expected:
                errors.append("marker %s in %s was modified by hand" % (token, rel))
                new_lines.append(line)
                continue
            if expected is None and rec_text and core != rec_text.rstrip("\r\n"):
                errors.append("marker %s in %s was modified by hand" % (token, rel))
                new_lines.append(line)
                continue
            used.add(token)
            # drop exact generated line
        if errors:
            continue
        new_text = _join_lines(new_lines, nl, trailing)
        path.write_bytes(new_text.encode("utf-8"))
    if errors:
        raise MarkerError("; ".join(errors))
    return sorted(by_file.keys())


STALE_MSG = (
    "the code you are editing is not the code that runs; "
    "read references/stale-code-checks.md before changing any logic"
)
