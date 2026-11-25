"""Backup, restore, configuration and log inspection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from . import logger
from .config import BACKUP_DIR, LOG_FILE, load_settings, save_settings
from .tools import ToolExecutor


@dataclass(frozen=True)
class OperationResult:
    success: bool
    message: str
    data: Dict[str, Any]


class OperationsCenter:
    def __init__(self, tools: ToolExecutor) -> None:
        self.tools = tools

    def backup(self, paths: List[str] | None = None) -> OperationResult:
        result = self.tools.execute("backup", {"paths": paths or []})
        return OperationResult(result.success, result.message, result.data)

    def list_backups(self) -> OperationResult:
        try:
            entries = sorted(
                (
                    {
                        "name": item.name,
                        "size": item.stat().st_size,
                        "created": item.stat().st_mtime,
                    }
                    for item in BACKUP_DIR.iterdir()
                    if item.is_file()
                ),
                key=lambda item: item["created"],
                reverse=True,
            )
        except OSError:
            entries = []
        return OperationResult(True, f"{len(entries)} backups found", {"backups": entries})

    def restore(self, archive: str, target: str | None = None) -> OperationResult:
        result = self.tools.execute(
            "restore_backup",
            {"archive": archive, "target": target or str(self.tools._default_workspace())},
        )
        return OperationResult(result.success, result.message, result.data)

    def config(self) -> OperationResult:
        settings = load_settings()
        safe = dict(settings)
        # Only the *name* of the key environment variable is ever shown.
        safe["online_key_env"] = settings.get("online_key_env", "")
        return OperationResult(True, "configuration read", {"settings": safe})

    def set_config(self, key: str, value: Any) -> OperationResult:
        allowed = set(load_settings().keys())
        if key not in allowed:
            return OperationResult(False, f"unknown setting: {key}", {})
        result = self.tools.execute("config_set", {"key": key, "value": value})
        return OperationResult(result.success, result.message, result.data)

    def log_tail(self, limit: int = 20) -> OperationResult:
        try:
            lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        return OperationResult(True, f"{len(lines[-limit:])} log entries", {"lines": lines[-limit:]})

    def log_stats(self) -> OperationResult:
        try:
            lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        counts: Dict[str, int] = {}
        for line in lines:
            try:
                event = json.loads(line).get("event", "unknown")
            except Exception:
                event = "unknown"
            counts[event] = counts.get(event, 0) + 1
        return OperationResult(True, f"log size: {len(lines)} entries", {"events": counts})
