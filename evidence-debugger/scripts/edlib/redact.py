"""Redact secrets from untrusted strings. Never raises."""

from __future__ import annotations

import os
import re
from typing import List, Pattern, Tuple

_KIND = "[REDACTED:%s]"

# Linear, bounded patterns. Avoid nested unbounded quantifiers.
_PATTERNS: List[Tuple[str, Pattern[str]]] = [
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    (
        "aws_secret",
        re.compile(
            r"(?i)aws_secret_access_key\s*[=:]\s*\S{6,256}"
        ),
    ),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{10,255}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{10,255}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{10,255}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{10,255}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,255}\b")),
    ("stripe_key", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{8,255}\b")),
    ("google_api_key", re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b")),
    (
        "jwt",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{4,512}\.[A-Za-z0-9_-]{4,2048}\.[A-Za-z0-9_-]{4,2048}\b"
        ),
    ),
    (
        "auth_header",
        re.compile(
            r"(?i)(Authorization\s*:\s*)(Bearer|Basic)\s+\S{6,4096}"
        ),
    ),
    (
        "pem_private",
        re.compile(
            r"-----BEGIN [A-Z ]{0,40}PRIVATE KEY-----[\s\S]{0,12000}-----END [A-Z ]{0,40}PRIVATE KEY-----"
        ),
    ),
    (
        "url_password",
        re.compile(
            r"([a-zA-Z][a-zA-Z0-9+.-]{0,24}://[^:@\s/]{1,256}:)([^@\s/]{1,512})(@)"
        ),
    ),
    (
        "key_value",
        re.compile(
            r"(?i)\b((?:password|passwd|secret|token|api[_-]?key|private[_-]?key)\s*[=:]\s*)(\S{6,512})"
        ),
    ),
]

_ENV_NAME_RE = re.compile(r"(?i)(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)")


def _env_secrets():
    out = []
    try:
        items = list(os.environ.items())
    except Exception:
        return out
    for name, value in items:
        try:
            if not value or len(value) < 8:
                continue
            if _ENV_NAME_RE.search(name):
                out.append(value)
        except Exception:
            continue
    # longest first so overlapping values redact fully
    out.sort(key=len, reverse=True)
    return out


def _sub_auth(m):
    try:
        return m.group(1) + m.group(2) + " " + (_KIND % "auth_header")
    except Exception:
        return _KIND % "auth_header"


def _sub_url(m):
    try:
        return m.group(1) + (_KIND % "url_password") + m.group(3)
    except Exception:
        return _KIND % "url_password"


def _sub_kv(m):
    try:
        return m.group(1) + (_KIND % "key_value")
    except Exception:
        return _KIND % "key_value"


def redact(text):
    """Return text with secrets replaced by [REDACTED:kind]. Never raises."""
    try:
        if text is None:
            return ""
        if not isinstance(text, str):
            text = str(text)
        if not text:
            return text
    except Exception:
        return ""
    try:
        for kind, pat in _PATTERNS:
            try:
                if kind == "auth_header":
                    text = pat.sub(_sub_auth, text)
                elif kind == "url_password":
                    text = pat.sub(_sub_url, text)
                elif kind == "key_value":
                    text = pat.sub(_sub_kv, text)
                else:
                    repl = _KIND % kind
                    text = pat.sub(repl, text)
            except Exception:
                continue
        for secret in _env_secrets():
            try:
                if secret and secret in text:
                    text = text.replace(secret, _KIND % "env")
            except Exception:
                continue
        return text
    except Exception:
        try:
            return str(text)
        except Exception:
            return ""
