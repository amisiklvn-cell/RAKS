import io
import unittest
from unittest.mock import patch

from raks.config import MENU_ITEMS
from raks.ui import TerminalUI

SAMPLE_STATUS = {
    "platform": "Linux",
    "architecture": "aarch64",
    "python": "3.14.10",
    "ram_total": "2.7 GB",
    "ram_available": "660.0 MB",
    "storage_free": "6.1 GB",
    "git": "available",
    "gh": "available",
    "ai_engine": "not loaded (Stage 2)",
    "mode": "offline-first",
}


class TerminalUITests(unittest.TestCase):
    def test_plain_output_has_no_ansi_in_non_tty(self):
        stream = io.StringIO()
        ui = TerminalUI(stream)
        ui.banner(SAMPLE_STATUS)
        ui.dashboard()
        self.assertNotIn("\033", stream.getvalue())
        self.assertIn("RAKS AI", stream.getvalue())
        self.assertIn("MAIN MENU", stream.getvalue())

    def test_dashboard_lists_all_ten_items(self):
        stream = io.StringIO()
        TerminalUI(stream).dashboard()
        output = stream.getvalue()
        for number, name in enumerate(MENU_ITEMS, start=1):
            self.assertIn(f"{number:>2}. {name}", output)

    def test_prompt_text(self):
        stream = io.StringIO()
        ui = TerminalUI(stream)
        with patch("builtins.input", return_value="hello"):
            value = ui.prompt()
        self.assertEqual(value, "hello")
        self.assertTrue(stream.getvalue().endswith("raks > "))

    def test_clear_and_not_implemented_are_explicit(self):
        stream = io.StringIO()
        ui = TerminalUI(stream)
        ui.clear()
        ui.not_implemented("Web Research")
        ui.error("bad input")
        output = stream.getvalue()
        self.assertIn("Screen cleared.", output)
        self.assertIn("Web Research: not implemented yet", output)
        self.assertIn("error: bad input", output)
