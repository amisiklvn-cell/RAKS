"""Privacy-safe operation logger.

Only event names and a small allowlist of metadata fields are written.
Prompts, credentials, authorization headers, raw paths, and tool arguments are
never logged. Existing log lines can be rewritten with ``sanitize_existing_log``
so historical records follow the same policy.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import LOG_FILE

_LOCK = threading.Lock()

# Only these fields may accompany an event. Anything else is discarded before
# serialization, so a caller cannot accidentally log a prompt or a secret.
SAFE_FIELDS = frozenset(
    {
        "version",
        "platform",
        "action",
        "route",
        "tool",
        "mode",
        "provider",
        "endpoint",
        "method",
        "status",
        "intent",
    }
)

SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret|password)\s*[:=]\s*)[^\s,;]+"),
)


def _redact(value: object) -> str:
    text = str(value)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(
            lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]",
            text,
        )
    return text[:120]


def log(event: str, **fields: object) -> None:
    """Append one sanitized JSON line. Logging failures are ignored."""
    record = {"time": datetime.now(timezone.utc).isoformat(), "event": _redact(event)[:80]}
    for key, value in fields.items():
        if key in SAFE_FIELDS:
            record[key] = _redact(value)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def sanitize_existing_log(path: str | None = None) -> int:
    """Rewrite an existing log with only privacy-safe fields.

    Returns the number of sanitized lines kept. Malformed lines are dropped.
    """
    target = LOG_FILE if path is None else Path(path)
    try:
        raw_lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0

    cleaned = []
    for line in raw_lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        safe = {
            "time": _redact(record.get("time", ""))[:120],
            "event": _redact(record.get("event", "unknown"))[:80],
        }
        for key in SAFE_FIELDS:
            if key in record:
                safe[key] = _redact(record[key])
        cleaned.append(json.dumps(safe, ensure_ascii=False) + "\n")

    temporary = target.with_name(target.name + ".sanitizing")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            temporary.write_text("".join(cleaned), encoding="utf-8")
            temporary.chmod(0o600)
            os.replace(str(temporary), str(target))
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return 0
    return len(cleaned)
