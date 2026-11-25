"""Small, safe operation logger.

Only event names and short metadata are written. User prompts and command
arguments are intentionally never logged.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from .config import LOG_FILE

_LOCK = threading.Lock()


def log(event: str, **fields: object) -> None:
    """Append one JSON line to the local state log. Failures are ignored."""
    record = {"time": datetime.now(timezone.utc).isoformat(), "event": event}
    for key, value in fields.items():
        record[key] = str(value)[:120]

    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass
