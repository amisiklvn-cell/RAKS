import tempfile
import unittest
from pathlib import Path

from raks.config import DB_FILE, WORKSPACE_ROOT
from raks.memory import MemoryStore


class MemoryTests(unittest.TestCase):
    def test_conversation_persists_after_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "memory.db")
            store = MemoryStore(path)
            store.remember("user", "remember this")
            store.remember("assistant", "remembered")
            store.close()

            reopened = MemoryStore(path)
            rows = reopened.recent(10)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["content"], "remembered")
            self.assertEqual(rows[1]["content"], "remember this")
            reopened.close()

    def test_active_conversation_and_isolation_persist_after_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "memory.db")
            store = MemoryStore(path)
            work = store.start_conversation("work")
            store.remember("user", "work secret")
            home = store.start_conversation("home")
            store.remember("user", "home secret")
            self.assertTrue(store.switch_conversation(work))
            store.close()

            reopened = MemoryStore(path)
            self.assertEqual(reopened.current_conversation, work)
            contents = [row["content"] for row in reopened.recent(20)]
            self.assertIn("work secret", contents)
            self.assertNotIn("home secret", contents)

            self.assertTrue(reopened.switch_conversation(home))
            contents = [row["content"] for row in reopened.recent(20)]
            self.assertIn("home secret", contents)
            self.assertNotIn("work secret", contents)
            self.assertGreaterEqual(len(reopened.conversations()), 2)
            reopened.close()

    def test_tasks_and_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(str(Path(tmp) / "memory.db"))
            self.assertTrue(store.record_task("build", "success", "done"))
            self.assertTrue(store.record_project("RAKS", str(WORKSPACE_ROOT), {"stage": 3}))
            self.assertEqual(store.recent_tasks(1)[0]["summary"], "build")
            self.assertEqual(store.stats()["projects"], 1)
            self.assertEqual(len(store.search("remember")), 0)
            store.close()

    def test_disabled_memory_is_honest(self):
        store = MemoryStore(enabled=False)
        result = store.remember("user", "hello")
        self.assertFalse(result.stored)
        self.assertIn("disabled", result.message.lower())
        self.assertEqual(store.recent(), [])

    def test_database_lives_outside_repository(self):
        self.assertFalse(str(DB_FILE).startswith(str(WORKSPACE_ROOT)))
