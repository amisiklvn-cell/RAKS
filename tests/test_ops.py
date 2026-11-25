import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from raks import config
from raks.approval import DenyGate
from tests import AutoGate
from raks.config import LOG_FILE, load_settings
from raks.ops import OperationsCenter
from raks.tools import ToolExecutor


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.backups = self.root / "backups"
        self.backups.mkdir()
        self.log = self.root / "raks.log"
        self.tools = ToolExecutor({"workspaces": [str(self.root)]}, AutoGate())
        self.ops = OperationsCenter(self.tools)

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_and_list(self):
        (self.root / "file.txt").write_text("data", encoding="utf-8")
        with patch("raks.tools.BACKUP_DIR", self.backups), \
             patch("raks.ops.BACKUP_DIR", self.backups):
            created = self.ops.backup([str(self.root / "file.txt")])
            self.assertTrue(created.success, created.message)
            listed = self.ops.list_backups()
        self.assertEqual(len(listed.data["backups"]), 1)

    def test_config_and_set_config(self):
        current = self.ops.config()
        self.assertTrue(current.success)
        self.assertIn("route_mode", current.data["settings"])
        with patch("raks.tools.save_settings") as save:
            result = self.ops.set_config("route_mode", "offline")
        self.assertTrue(result.success)
        self.assertTrue(save.called)

    def test_unknown_setting_is_rejected(self):
        result = self.ops.set_config("delete_everything", "yes")
        self.assertFalse(result.success)

    def test_log_tail_and_stats(self):
        self.log.write_text(
            json.dumps({"time": "t", "event": "chat"}) + "\n"
            + json.dumps({"time": "t", "event": "startup"}) + "\n",
            encoding="utf-8",
        )
        with patch("raks.ops.LOG_FILE", self.log):
            tail = self.ops.log_tail()
            stats = self.ops.log_stats()
        self.assertEqual(len(tail.data["lines"]), 2)
        self.assertEqual(stats.data["events"]["chat"], 1)

    def test_restore_requires_approval(self):
        with patch("raks.ops.BACKUP_DIR", self.backups):
            denied = OperationsCenter(
                ToolExecutor({"workspaces": [str(self.root)]}, DenyGate())
            ).restore("none.tar.gz")
        self.assertFalse(denied.success)

    def test_invalid_archive_is_rejected_safely(self):
        with patch("raks.tools.BACKUP_DIR", self.backups), patch("raks.ops.BACKUP_DIR", self.backups):
            bad = self.backups / "bad.tar.gz"
            bad.write_text("garbage", encoding="utf-8")
            result = OperationsCenter(self.tools).restore(str(bad), str(self.root))
        self.assertFalse(result.success)
        self.assertIn("ReadError", result.message)

    def test_traversal_entries_are_counted_as_skipped(self):
        with patch("raks.tools.BACKUP_DIR", self.backups), patch("raks.ops.BACKUP_DIR", self.backups):
            archive = self.backups / "traversal.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                info = tarfile.TarInfo("../escaped.txt")
                data = b"bad"
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            result = OperationsCenter(self.tools).restore(str(archive), str(self.root))
        self.assertTrue(result.success)
        self.assertEqual(result.data["restored"], 0)
        self.assertEqual(result.data["skipped"], 1)
        self.assertFalse((self.root.parent / "escaped.txt").exists())

    def test_symlink_escape_archives_are_rejected(self):
        for label, linkname in (
            ("absolute", "/etc/passwd"),
            ("relative", "../outside-target.txt"),
        ):
            with self.subTest(label=label), patch("raks.tools.BACKUP_DIR", self.backups), \
                 patch("raks.ops.BACKUP_DIR", self.backups):
                archive = self.backups / f"symlink-{label}.tar.gz"
                with tarfile.open(archive, "w:gz") as tar:
                    info = tarfile.TarInfo("link.txt")
                    info.type = tarfile.SYMTYPE
                    info.linkname = linkname
                    tar.addfile(info)
                result = OperationsCenter(self.tools).restore(str(archive), str(self.root))
            self.assertFalse(result.success, result.message)
            self.assertFalse((self.root / "link.txt").exists())

    def test_config_file_is_private_atomically(self):
        target = self.root / "config.json"
        with patch.object(config, "CONFIG_FILE", target):
            saved = config.save_settings({"route_mode": "offline"})
        self.assertEqual(saved, target)
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        self.assertFalse(target.with_name(target.name + ".tmp").exists())

    def test_backup_restore_round_trip(self):
        with patch("raks.tools.BACKUP_DIR", self.backups), \
             patch("raks.ops.BACKUP_DIR", self.backups):
            (self.root / "note.txt").write_text("restore me", encoding="utf-8")
            created = self.ops.backup([str(self.root / "note.txt")])
            self.assertTrue(created.success, created.message)
            (self.root / "note.txt").unlink()
            restored = self.ops.restore(created.data["archive"], str(self.root))
            self.assertTrue(restored.success, restored.message)
            self.assertEqual((self.root / "note.txt").read_text(encoding="utf-8"), "restore me")
