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
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
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
            self._connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
            self._connection.commit()
            active = self._get_state("active_conversation")
            if active and self._conversation_exists(active):
                self.current_conversation = active
                return
            previous = self._connection.execute(
                "SELECT id FROM conversations ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            if previous:
                self.current_conversation = previous[0]
                self._set_state("active_conversation", previous[0])
            else:
                self.start_conversation("default")

    def _disabled(self, what: str) -> MemoryResult:
        return MemoryResult(False, f"Memory is disabled; {what} was not stored.")

    def _get_state(self, key: str) -> str:
        if self._connection is None:
            return ""
        row = self._connection.execute(
            "SELECT value FROM state WHERE key = ?", (key,)
        ).fetchone()
        return str(row[0]) if row else ""

    def _set_state(self, key: str, value: str) -> None:
        if self._connection is None:
            return
        self._connection.execute(
            "INSERT INTO state(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        self._connection.commit()

    def _conversation_exists(self, conversation_id: str) -> bool:
        if self._connection is None:
            return False
        row = self._connection.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        return row is not None

    def conversations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return conversations with counts, newest first; flag the active one."""
        if not self.enabled or self._connection is None:
            return []
        cursor = self._connection.execute(
            "SELECT c.id, c.title, c.created_at, COUNT(m.id) AS messages "
            "FROM conversations c LEFT JOIN messages m ON m.conversation_id = c.id "
            "GROUP BY c.id ORDER BY c.rowid DESC LIMIT ?",
            (max(1, min(int(limit), 100)),),
        )
        return [
            {
                "id": row[0],
                "title": row[1],
                "created_at": row[2],
                "messages": int(row[3]),
                "active": row[0] == self.current_conversation,
            }
            for row in cursor.fetchall()
        ]

    def start_conversation(self, title: str = "default") -> str:
        if not self.enabled or self._connection is None:
            return ""
        conversation_id = uuid.uuid4().hex
        self._connection.execute(
            "INSERT INTO conversations(id, title, created_at) VALUES (?, ?, ?)",
            (conversation_id, title or "default", _now()),
        )
        self._connection.commit()
        self.current_conversation = conversation_id
        self._set_state("active_conversation", conversation_id)
        return conversation_id

    def switch_conversation(self, conversation_id: str) -> bool:
        """Switch the active conversation without deleting or overwriting any."""
        if not self.enabled or self._connection is None:
            return False
        if not self._conversation_exists(str(conversation_id)):
            return False
        self.current_conversation = str(conversation_id)
        self._set_state("active_conversation", self.current_conversation)
        return True

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

    def recent_projects(self, limit: int = 10) -> List[Dict[str, str]]:
        if not self.enabled or self._connection is None:
            return []
        cursor = self._connection.execute(
            "SELECT name, path, created_at FROM projects ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 100)),),
        )
        return [
            {"name": row[0], "path": row[1], "created_at": row[2]}
            for row in cursor.fetchall()
        ]

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
