import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import AutoGate
from raks.app import RaksApp
from raks.commands import CommandResult
from raks.core import RAKSCore
from raks.engine import EngineResponse
from raks.memory import MemoryStore
from raks.tools import ToolExecutor
from tests.test_ui import SAMPLE_STATUS


class FakeEngine:
    def __init__(self, available=True):
        self.available = available
        self.calls = []

    def status(self):
        return {"mode": "auto", "local": "fake", "online": "fake"}

    def respond(self, prompt, history=None):
        self.calls.append((prompt, history or []))
        if self.available:
            return EngineResponse(True, "AI answer", "local", "fake", "model", 5)
        return EngineResponse(True, "AI unavailable", "unavailable", error="test")


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.engine = FakeEngine()
        self.memory = MemoryStore(str(self.root / "memory.db"))
        self.tools = ToolExecutor({"workspaces": [str(self.root)]}, AutoGate())
        self.settings = {"web_host": "127.0.0.1", "web_port": 8765}
        self.core = RAKSCore(self.settings, self.engine, self.memory, self.tools)

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def make_app(self, stream=None):
        with patch("raks.app.system.collect_system_status", return_value=SAMPLE_STATUS), \
             patch("raks.app.logger.log"):
            return RaksApp(stream or io.StringIO(), core=self.core, settings=self.settings)

    def run_lines(self, lines):
        stream = io.StringIO()
        with patch("raks.app.system.collect_system_status", return_value=SAMPLE_STATUS), \
             patch("raks.app.logger.log"), \
             patch("builtins.input", side_effect=lines):
            app = RaksApp(stream, core=self.core, settings=self.settings)
            app.run()
        return stream.getvalue()

    def test_full_loop_handles_commands_and_exits(self):
        output = self.run_lines(["/status", "hello", "99", "/bad", "/help", "/exit"])
        self.assertIn("SYSTEM STATUS", output)
        self.assertIn("AI answer", output)
        self.assertIn("'99' is not a menu option", output)
        self.assertIn("unknown command '/bad'", output)
        self.assertIn("COMMANDS", output)
        self.assertTrue(output.rstrip().endswith("Goodbye."))

    def test_dispatch_empty_and_unknown(self):
        app = self.make_app()
        self.assertTrue(app.dispatch(CommandResult("empty")))
        self.assertTrue(app.dispatch(CommandResult("unknown_command", "/nope")))
        self.assertFalse(app.dispatch(CommandResult("exit")))

    def test_chat_stores_history_through_shared_core(self):
        app = self.make_app()
        app.dispatch(CommandResult("chat", "remember me"))
        self.assertEqual(len(self.core.history()), 2)
        self.assertEqual(self.engine.calls[0][0], "remember me")

    def test_offline_answer_is_reported_as_error(self):
        self.engine.available = False
        stream = io.StringIO()
        app = self.make_app(stream)
        app.dispatch(CommandResult("chat", "hello"))
        self.assertIn("error: AI unavailable", stream.getvalue())

    def test_menu_sections_do_not_claim_unimplemented(self):
        stream = io.StringIO()
        app = self.make_app(stream)
        for number in map(str, range(1, 11)):
            app.dispatch(CommandResult("menu_item", number))
        output = stream.getvalue()
        self.assertNotIn("not implemented yet", output)
        self.assertIn("CODING ASSISTANT", output)
        self.assertIn("python", output)
        self.assertIn("TERMINAL TOOLS", output)
        self.assertIn("Arbitrary natural-language shell execution is disabled", output)

    def test_tools_and_history_commands(self):
        stream = io.StringIO()
        app = self.make_app(stream)
        app.dispatch(CommandResult("tools"))
        app.dispatch(CommandResult("history"))
        output = stream.getvalue()
        self.assertIn("write_file", output)
        self.assertIn("RECENT HISTORY", output)

    def test_config_and_ops_commands(self):
        stream = io.StringIO()
        app = self.make_app(stream)
        app.dispatch(CommandResult("config", ""))
        app.dispatch(CommandResult("ops", "stats"))
        output = stream.getvalue()
        self.assertIn("route_mode", output)
        self.assertIn("LOG STATS", output)

    def test_code_languages_and_automation_list(self):
        stream = io.StringIO()
        app = self.make_app(stream)
        app.dispatch(CommandResult("code", "languages"))
        app.dispatch(CommandResult("automate", ""))
        output = stream.getvalue()
        self.assertIn("python", output)
        self.assertIn("AUTOMATIONS", output)

    def test_web_status_without_server(self):
        stream = io.StringIO()
        app = self.make_app(stream)
        app.dispatch(CommandResult("web", "status"))
        self.assertIn("not running", stream.getvalue())

    def test_conversation_plan_and_project_commands(self):
        stream = io.StringIO()
        app = self.make_app(stream)
        app.dispatch(CommandResult("conversation", "new work"))
        app.dispatch(CommandResult("conversation", "list"))
        app.dispatch(CommandResult("plan", ""))
        app.dispatch(CommandResult("plan", "backup"))
        app.dispatch(CommandResult("project", "add demo /tmp/demo"))
        app.dispatch(CommandResult("project", "task test task"))
        app.dispatch(CommandResult("project", "list"))
        output = stream.getvalue()
        self.assertIn("created conversation", output)
        self.assertIn("CONVERSATIONS", output)
        self.assertIn("PLANNED INTENTS", output)
        self.assertIn("PLAN: Back up the approved workspace", output)
        self.assertIn("project recorded", output)
        self.assertIn("task recorded", output)
        self.assertIn("[open] test task", output)
        self.assertIn("PROJECTS", output)

    def test_plan_run_uses_tools(self):
        stream = io.StringIO()
        app = self.make_app(stream)
        app.dispatch(CommandResult("plan", "run status"))
        self.assertIn("tool executor ready", stream.getvalue())

    def test_non_loopback_web_host_falls_back(self):
        stream = io.StringIO()
        settings = {"web_host": "0.0.0.0", "web_port": 0}
        with patch("raks.app.system.collect_system_status", return_value=SAMPLE_STATUS), \
             patch("raks.app.logger.log"):
            app = RaksApp(stream, core=self.core, settings=settings)
            app.dispatch(CommandResult("web", "start"))
            app.dispatch(CommandResult("web", "stop"))
        self.assertIn("using 127.0.0.1", stream.getvalue())

    def test_backup_lists_without_archive(self):
        stream = io.StringIO()
        app = self.make_app(stream)
        with patch("raks.ops.BACKUP_DIR", self.root / "backups"):
            app.dispatch(CommandResult("restore", ""))
        self.assertIn("No backups found", stream.getvalue())
