import unittest

from raks.engine import AIEngine
from raks.memory import MemoryStore
from raks.planner import DevelopmentCommandCenter
from raks.tools import ToolExecutor


class BoundaryTests(unittest.TestCase):
    def test_engine_is_not_fake(self):
        response = AIEngine().respond("write a poem")
        self.assertFalse(response.implemented)
        self.assertIn("not implemented", response.text.lower())

    def test_tool_executor_executes_nothing(self):
        result = ToolExecutor().execute("execute_command", {"command": "echo hi"})
        self.assertFalse(result.implemented)
        self.assertFalse(result.success)

    def test_sensitive_operations_require_approval(self):
        executor = ToolExecutor()
        for tool in ("write_file", "install", "build", "git_push", "execute_command"):
            with self.subTest(tool=tool):
                self.assertTrue(executor.requires_approval(tool))
        self.assertFalse(executor.requires_approval("read_status"))

    def test_command_center_refuses(self):
        with self.assertRaises(NotImplementedError):
            DevelopmentCommandCenter().interpret("build an app")

    def test_memory_creates_nothing(self):
        result = MemoryStore().remember("user", "hello")
        self.assertFalse(result.stored)
        self.assertIn("not implemented", result.message.lower())
