import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from raks.approval import DenyGate
from raks.tools import ToolExecutor
from tests import AutoGate


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "workspace"
        self.root.mkdir()
        self.backups = Path(self.tmp.name) / "backups"
        self.settings = {"workspaces": [str(self.root)]}

    def tearDown(self):
        self.tmp.cleanup()

    def make_executor(self, gate=None):
        return ToolExecutor(self.settings, gate or AutoGate())

    def test_read_only_tools_need_no_approval(self):
        executor = self.make_executor(DenyGate())
        result = executor.execute("status")
        self.assertTrue(result.success)

    def test_write_requires_approval(self):
        executor = self.make_executor(DenyGate())
        result = executor.execute("write_file", {"path": "a.txt", "content": "hello"})
        self.assertFalse(result.success)
        self.assertFalse((self.root / "a.txt").exists())

    def test_write_creates_backup_before_overwrite(self):
        with patch("raks.tools.BACKUP_DIR", self.backups):
            executor = self.make_executor()
            executor.execute("write_file", {"path": "a.txt", "content": "one"})
            changed = executor.execute("write_file", {"path": "a.txt", "content": "two"})
        self.assertTrue(changed.success)
        self.assertEqual((self.root / "a.txt").read_text(), "two")
        self.assertEqual(len(list(self.backups.glob("a.txt.*.bak"))), 1)

    def test_path_outside_workspace_is_rejected(self):
        executor = self.make_executor()
        outside = str(Path(self.tmp.name) / "outside.txt")
        result = executor.execute("write_file", {"path": outside, "content": "no"})
        self.assertFalse(result.success)
        self.assertIn("outside approved workspace", result.message)

    def test_delete_backs_up_first(self):
        with patch("raks.tools.BACKUP_DIR", self.backups):
            executor = self.make_executor()
            executor.execute("write_file", {"path": "b.txt", "content": "data"})
            deleted = executor.execute("delete_file", {"path": "b.txt"})
        self.assertTrue(deleted.success)
        self.assertFalse((self.root / "b.txt").exists())
        self.assertEqual(len(list(self.backups.glob("b.txt.*.bak"))), 1)

    def test_arbitrary_command_execution_disabled(self):
        executor = self.make_executor()
        result = executor.execute("execute_command", {"command": "echo hi"})
        self.assertFalse(result.success)
        self.assertIn("disabled", result.message)

    def test_list_and_read_file(self):
        (self.root / "c.txt").write_text("content", encoding="utf-8")
        executor = self.make_executor()
        listing = executor.execute("list_dir")
        reading = executor.execute("read_file", {"path": "c.txt"})
        self.assertTrue(listing.success)
        self.assertTrue(any(item["name"] == "c.txt" for item in listing.data["entries"]))
        self.assertEqual(reading.data["content"], "content")

    def test_git_commit_requires_explicit_paths(self):
        executor = self.make_executor()
        with patch.object(executor, "_run") as run:
            result = executor.execute("git_commit", {"message": "test"})
        self.assertFalse(result.success)
        self.assertIn("explicit", result.message)
        run.assert_not_called()
        source = (Path(__file__).parent.parent / "raks" / "tools.py").read_text(encoding="utf-8")
        self.assertNotIn('"git", "add", "-A"', source)

    def test_unknown_tool_is_not_implemented(self):
        executor = self.make_executor()
        result = executor.execute("fly_to_moon")
        self.assertFalse(result.implemented)
        self.assertFalse(result.success)
