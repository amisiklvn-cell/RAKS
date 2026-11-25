"""Memory boundary for Stage 3.

SQLite will be used later. No database file is created in v0.1.0 so that no
personal data is written or committed during the foundation stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MemoryResult:
    stored: bool
    message: str


class MemoryStore:
    SCHEMA_VERSION = 1

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path
        self.enabled = False

    def remember(self, role: str, content: str) -> MemoryResult:
        return MemoryResult(False, "Memory & History is not implemented yet in v0.1.0.")

    def recent(self, limit: int = 10) -> list:
        return []
