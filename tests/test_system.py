import tempfile
import unittest
from pathlib import Path

from raks.system import collect_system_status, disk_info, format_bytes, parse_meminfo


class SystemTests(unittest.TestCase):
    def test_parse_meminfo(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "meminfo"
            path.write_text(
                "MemTotal:        2872568 kB\nMemAvailable:     677248 kB\nHugePages_Total:       0\n",
                encoding="utf-8",
            )
            parsed = parse_meminfo(str(path))
        self.assertEqual(parsed["MemTotal"], 2872568)
        self.assertEqual(parsed["MemAvailable"], 677248)

    def test_format_bytes(self):
        self.assertEqual(format_bytes(None), "unknown")
        self.assertEqual(format_bytes(512), "512 B")
        self.assertEqual(format_bytes(2048), "2.0 KB")

    def test_status_has_required_keys(self):
        status = collect_system_status()
        for key in ("platform", "architecture", "python", "ai_engine", "mode"):
            self.assertIn(key, status)
        self.assertEqual(status["mode"], "offline-first")

    def test_disk_info(self):
        info = disk_info()
        self.assertIn("free_bytes", info)
        self.assertIn("total_bytes", info)
