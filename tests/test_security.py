import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path

from raks.security import scan_workspace


class SecurityTests(unittest.TestCase):
    def test_clean_workspace_has_no_critical_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "main.py").write_text("print('ok')\n", encoding="utf-8")
            report = scan_workspace(tmp)
            self.assertEqual(report.files_scanned, 1)
            self.assertFalse(any(f["severity"] == "critical" for f in report.findings))
            self.assertIn("DEFENSIVE SECURITY REPORT", report.text)

    def test_detects_possible_secret_and_sensitive_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".env").write_text(
                "TOKEN=ghp_" + "a" * 30 + "\n", encoding="utf-8"
            )
            report = scan_workspace(tmp)
            kinds = {item["kind"] for item in report.findings}
            self.assertIn("possible_secret", kinds)
            self.assertIn("sensitive_filename", kinds)
            self.assertTrue(any(item["severity"] == "critical" for item in report.findings))

    def test_detects_world_writable_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "loose.txt"
            path.write_text("x", encoding="utf-8")
            path.chmod(stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            report = scan_workspace(tmp)
            self.assertIn("world_writable", {item["kind"] for item in report.findings})

    def test_scan_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.txt"
            path.write_text("unchanged", encoding="utf-8")
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            scan_workspace(tmp)
            after = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(before, after)

    def test_missing_directory_is_reported(self):
        report = scan_workspace("/definitely/not/a/real/path/raks")
        self.assertIn("not a directory", report.summary)
