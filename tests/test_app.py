import io
import unittest
from unittest.mock import patch

from raks.app import RaksApp
from raks.commands import CommandResult
from raks.engine import EngineResponse
from tests.test_ui import SAMPLE_STATUS


class FakeEngine:
    def respond(self, prompt, history=None):
        return EngineResponse(
            implemented=True,
            text="AI unavailable in test",
            route="unavailable",
            error="test",
        )


class AppTests(unittest.TestCase):
    def make_app(self, stream):
        with patch("raks.app.engine.HybridAIEngine", return_value=FakeEngine()), \
             patch("raks.app.system.collect_system_status", return_value=SAMPLE_STATUS), \
             patch("raks.app.logger.log"):
            return RaksApp(stream)

    def test_full_loop_handles_commands_and_exits(self):
        stream = io.StringIO()
        with patch("raks.app.engine.HybridAIEngine", return_value=FakeEngine()), \
             patch("raks.app.system.collect_system_status", return_value=SAMPLE_STATUS), \
             patch("raks.app.logger.log"), \
             patch("builtins.input", side_effect=["/status", "1", "99", "/help", "/exit"]):
            app = RaksApp(stream)
            app.run()

        output = stream.getvalue()
        self.assertIn("SYSTEM STATUS", output)
        self.assertIn("AI unavailable in test", output)
        self.assertIn("'99' is not a menu option", output)
        self.assertIn("COMMANDS", output)
        self.assertTrue(output.rstrip().endswith("Goodbye."))

    def test_dispatch_empty_and_unknown(self):
        app = self.make_app(io.StringIO())
        self.assertTrue(app.dispatch(CommandResult("empty")))
        self.assertTrue(app.dispatch(CommandResult("unknown_command", "/nope")))
        self.assertFalse(app.dispatch(CommandResult("exit")))
