"""Failure fingerprinting from captured output. Pure functions."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional

_ERROR_WORD = re.compile(
    r"(?i)\b(error|exception|fatal|panic|failed|assertion)\b"
)
_TS_ERROR = re.compile(r"(?i)\berror TS\d+\b")
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_ISO = re.compile(
    r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b"
)
_HEX_ADDR = re.compile(r"\b0x[0-9a-fA-F]+\b")
_PATH = re.compile(
    r"(?P<p>(?:[A-Za-z]:)?(?:[/\\][^\s:]+)+)"
)
_DIGITS = re.compile(r"\d+")
_WS = re.compile(r"\s+")


def last_nonempty(text: str) -> str:
    """Return last non-empty line of text."""
    if not text:
        return ""
    for line in reversed(text.splitlines()):
        if line.strip():
            return line.rstrip()
    return ""


def extract_python_traceback_line(text: str) -> Optional[str]:
    """Last exception line of the last Python traceback, if present."""
    if not text:
        return None
    idx = text.rfind("Traceback (most recent call last):")
    if idx < 0:
        return None
    rest = text[idx:]
    lines = rest.splitlines()
    last = None
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("File ") or line.startswith(" ") or line.startswith("\t"):
            continue
        last = stripped
    return last


def extract_error_line(stdout: str, stderr: str) -> str:
    """Pick the last error-like line from captured streams."""
    combined = (stderr or "") + "\n" + (stdout or "")
    py = extract_python_traceback_line(combined)
    if py:
        return py
    ts_hit = None
    err_hit = None
    for blob in (stderr, stdout):
        if not blob:
            continue
        for line in blob.splitlines():
            if _TS_ERROR.search(line):
                ts_hit = line.rstrip()
            elif _ERROR_WORD.search(line):
                err_hit = line.rstrip()
    if ts_hit:
        return ts_hit
    if err_hit:
        return err_hit
    last_err = last_nonempty(stderr or "")
    if last_err:
        return last_err
    return last_nonempty(stdout or "")


def _basename_path(match):
    raw = match.group("p")
    try:
        name = Path(raw).name
    except Exception:
        name = raw.replace("\\", "/").split("/")[-1]
    return name


def normalize_line(line: str) -> str:
    """Normalize an error line for stable fingerprints."""
    if line is None:
        line = ""
    text = line
    text = _PATH.sub(_basename_path, text)
    text = _UUID.sub("UUID", text)
    text = _ISO.sub("TS", text)
    text = _HEX_ADDR.sub("\x00HEX\x00", text)
    text = _DIGITS.sub("N", text)
    text = text.replace("\x00HEX\x00", "0xX")
    text = _WS.sub(" ", text).strip().lower()
    return text


def exit_code_class(exit_code, timed_out=False) -> str:
    """Classify an exit as 0, nonzero, or timeout."""
    if timed_out:
        return "timeout"
    if exit_code == 0:
        return "0"
    return "nonzero"


def fingerprint(stdout: str, stderr: str, exit_code, timed_out=False) -> str:
    """Return 12 hex chars of SHA-256(normalized_line|class)."""
    line = extract_error_line(stdout, stderr)
    norm = normalize_line(line)
    klass = exit_code_class(exit_code, timed_out=timed_out)
    payload = "%s|%s" % (norm, klass)
    digest = hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()
    return digest[:12]


def compare_to_baseline(fp: str, baseline_fp: Optional[str], timed_out: bool,
                        passed: bool, same_command: bool) -> str:
    """Return SAME FAILURE, DIFFERENT FAILURE, PASSING, TIMEOUT, or DIFFERENT COMMAND."""
    if timed_out:
        return "TIMEOUT"
    if not same_command:
        return "DIFFERENT COMMAND"
    if passed:
        return "PASSING"
    if baseline_fp and fp == baseline_fp:
        return "SAME FAILURE"
    return "DIFFERENT FAILURE"
