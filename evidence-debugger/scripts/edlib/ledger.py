"""Append-only JSONL ledger with a cross-platform advisory lock."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .redact import redact

EVENT_TYPES = (
    "init",
    "repro",
    "hypothesis",
    "hypothesis_update",
    "attempt",
    "assumption",
    "marker_add",
    "marker_remove",
    "approval",
    "breaker_ack",
    "proof",
    "note",
    "allow_unsafe",
    "breaker_show",
    "envinfo",
)


class LedgerError(RuntimeError):
    """Ledger I/O failure."""


class FileLock(object):
    """Advisory lock: fcntl, msvcrt, or O_EXCL lockfile with 30s stale timeout."""

    def __init__(self, path: Path, stale_s: float = 30.0):
        self.path = path
        self.stale_s = stale_s
        self._fp = None  # type: Optional[Any]
        self._mode = None  # type: Optional[str]
        self._fd = None  # type: Optional[int]

    def acquire(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        last_err = None  # type: Optional[BaseException]
        while time.time() < deadline:
            try:
                if self._try_fcntl():
                    return
                if self._try_msvcrt():
                    return
                if self._try_excl():
                    return
            except Exception as exc:
                last_err = exc
            time.sleep(0.05)
        raise LedgerError("could not acquire lock: %s" % (last_err,))

    def _try_fcntl(self) -> bool:
        try:
            import fcntl
        except ImportError:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fp = open(str(self.path), "a+")
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError):
            fp.close()
            return False
        self._fp = fp
        self._mode = "fcntl"
        return True

    def _try_msvcrt(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import msvcrt
        except ImportError:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_RDWR | os.O_CREAT
        fd = os.open(str(self.path), flags, 0o600)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            os.close(fd)
            return False
        self._fd = fd
        self._mode = "msvcrt"
        return True

    def _try_excl(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                age = time.time() - self.path.stat().st_mtime
            except OSError:
                age = 0
            if age > self.stale_s:
                try:
                    self.path.unlink()
                except OSError:
                    return False
            else:
                return False
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(str(self.path), flags, 0o600)
        except OSError:
            return False
        self._fd = fd
        self._mode = "excl"
        return True

    def release(self) -> None:
        mode = self._mode
        self._mode = None
        if mode == "fcntl" and self._fp is not None:
            try:
                import fcntl

                fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                self._fp.close()
            except Exception:
                pass
            self._fp = None
        if mode == "msvcrt" and self._fd is not None:
            try:
                import msvcrt

                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
        if mode == "excl":
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except Exception:
                    pass
                self._fd = None
            try:
                self.path.unlink()
            except OSError:
                pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False


def _utcnow_iso() -> str:
    now = datetime.now(timezone.utc)
    # seconds precision plus Z
    return now.replace(microsecond=(now.microsecond // 1000) * 1000).isoformat().replace("+00:00", "Z")


def _posix_private_file(path: Path) -> None:
    if os.name == "posix" and path.exists():
        try:
            os.chmod(str(path), 0o600)
        except OSError:
            pass


class Ledger(object):
    """Append-only JSONL event store."""

    def __init__(self, path: Path):
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self._warned_corrupt = False

    def _open_append(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_WRONLY | os.O_APPEND
        fd = os.open(str(self.path), flags, 0o600)
        _posix_private_file(self.path)
        return os.fdopen(fd, "a", encoding="utf-8", newline="\n")

    def read_events(self, warn=None) -> List[Dict[str, Any]]:
        """Read events. Skip unparsable lines (especially a partial last line)."""
        if not self.path.exists():
            return []
        try:
            raw = self.path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise LedgerError("cannot read ledger: %s" % exc)
        events = []  # type: List[Dict[str, Any]]
        lines = raw.split("\n")
        nonempty_idx = [i for i, ln in enumerate(lines) if ln.strip()]
        last_i = nonempty_idx[-1] if nonempty_idx else -1
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                if warn is not None and not self._warned_corrupt:
                    if i == last_i:
                        warn("ed: warning: skipping corrupted last ledger line")
                    else:
                        warn("ed: warning: skipping corrupted ledger line")
                    self._warned_corrupt = True
                continue
            if isinstance(obj, dict):
                events.append(obj)
        return events

    def last_seq(self, events: Optional[List[Dict[str, Any]]] = None) -> int:
        if events is None:
            events = self.read_events()
        seq = 0
        for ev in events:
            try:
                s = int(ev.get("seq", 0))
            except (TypeError, ValueError):
                s = 0
            if s > seq:
                seq = s
        return seq

    def append(self, event_type: str, data: Dict[str, Any], warn=None) -> Dict[str, Any]:
        """Append one event. Returns the stored event dict."""
        payload = _redact_data(data)
        with FileLock(self.lock_path):
            events = self.read_events(warn=warn)
            seq = self.last_seq(events) + 1
            event = {
                "seq": seq,
                "ts": _utcnow_iso(),
                "type": event_type,
                "data": payload,
            }
            line = json.dumps(event, ensure_ascii=True, separators=(",", ":"))
            fp = self._open_append()
            try:
                fp.write(line + "\n")
                fp.flush()
                os.fsync(fp.fileno())
            finally:
                fp.close()
            _posix_private_file(self.path)
            return event


def _redact_data(obj):
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, list):
        return [_redact_data(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _redact_data(v) for k, v in obj.items()}
    return obj


def render_markdown(events: List[Dict[str, Any]]) -> str:
    """Render ledger.md from events. Never used as an input parser."""
    lines = ["# evidence-debugger ledger", ""]
    for ev in events:
        ts = ev.get("ts", "")
        typ = ev.get("type", "")
        seq = ev.get("seq", "")
        data = ev.get("data", {})
        lines.append("## %s  seq=%s  %s" % (typ, seq, ts))
        try:
            body = json.dumps(data, indent=2, ensure_ascii=True)
        except Exception:
            body = str(data)
        lines.append("```")
        lines.append(body)
        lines.append("```")
        lines.append("")
    return "\n".join(lines)
