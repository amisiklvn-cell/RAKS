"""SQLite conversation memory and project history.

The database lives outside the repository so personal data is never committed.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DB_FILE

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary TEXT NOT NULL,
    status TEXT NOT NULL,
    output TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
"""


@dataclass(frozen=True)
class MemoryResult:
    stored: bool
    message: str
    conversation_id: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    SCHEMA_VERSION = 2

    def __init__(self, path: Optional[str] = None, enabled: bool = True) -> None:
        self.path = Path(path) if path else DB_FILE
        self.enabled = enabled
        self._connection: Optional[sqlite3.Connection] = None
        self.current_conversation: Optional[str] = None
        if self.enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.path.chmod(0o600)
            except OSError:
                pass
            self._connection = sqlite3.connect(str(self.path), check_same_thread=False)
            self._connection.executescript(SCHEMA)
            self._connection.commit()
            previous = self._connection.execute(
                "SELECT id FROM conversations ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            self.current_conversation = previous[0] if previous else self.start_conversation("default")

    def _disabled(self, what: str) -> MemoryResult:
        return MemoryResult(False, f"Memory is disabled; {what} was not stored.")

    def start_conversation(self, title: str = "default") -> str:
        conversation_id = uuid.uuid4().hex
        assert self._connection is not None
        self._connection.execute(
            "INSERT INTO conversations(id, title, created_at) VALUES (?, ?, ?)",
            (conversation_id, title or "default", _now()),
        )
        self._connection.commit()
        self.current_conversation = conversation_id
        return conversation_id

    def remember(
        self,
        role: str,
        content: str,
        conversation_id: Optional[str] = None,
    ) -> MemoryResult:
        if not self.enabled or self._connection is None:
            return self._disabled("message")
        conversation = conversation_id or self.current_conversation
        if not conversation:
            conversation = self.start_conversation("default")
        self._connection.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation, role, content, _now()),
        )
        self._connection.commit()
        return MemoryResult(True, "stored", conversation)

    def recent(
        self,
        limit: int = 10,
        conversation_id: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        if not self.enabled or self._connection is None:
            return []
        conversation = conversation_id or self.current_conversation
        cursor = self._connection.execute(
            "SELECT role, content, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation, max(1, min(int(limit), 100))),
        )
        return [
            {"role": row[0], "content": row[1], "created_at": row[2]}
            for row in cursor.fetchall()
        ]

    def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        if not self.enabled or self._connection is None:
            return []
        cursor = self._connection.execute(
            "SELECT role, content, created_at FROM messages WHERE content LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (f"%{query}%", max(1, min(int(limit), 100))),
        )
        return [
            {"role": row[0], "content": row[1], "created_at": row[2]}
            for row in cursor.fetchall()
        ]

    def record_task(self, summary: str, status: str, output: str = "") -> bool:
        if not self.enabled or self._connection is None:
            return False
        self._connection.execute(
            "INSERT INTO tasks(summary, status, output, created_at) VALUES (?, ?, ?, ?)",
            (summary[:500], status[:50], output[:4000], _now()),
        )
        self._connection.commit()
        return True

    def recent_tasks(self, limit: int = 10) -> List[Dict[str, str]]:
        if not self.enabled or self._connection is None:
            return []
        cursor = self._connection.execute(
            "SELECT summary, status, output, created_at FROM tasks ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 100)),),
        )
        return [
            {"summary": row[0], "status": row[1], "output": row[2], "created_at": row[3]}
            for row in cursor.fetchall()
        ]

    def record_project(self, name: str, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        if not self.enabled or self._connection is None:
            return False
        self._connection.execute(
            "INSERT INTO projects(name, path, metadata, created_at) VALUES (?, ?, ?, ?)",
            (name[:200], path[:500], json.dumps(metadata or {}), _now()),
        )
        self._connection.commit()
        return True

    def stats(self) -> Dict[str, int]:
        if not self.enabled or self._connection is None:
            return {"enabled": 0}
        counts = {}
        for table in ("conversations", "messages", "tasks", "projects"):
            row = self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = int(row[0])
        counts["enabled"] = 1
        return counts

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
