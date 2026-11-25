import unittest

from raks.tools import APPROVAL_REQUIRED, ToolExecutor


class BoundaryTests(unittest.TestCase):
    def test_sensitive_operations_require_approval(self):
        for tool in ("write_file", "install", "build", "git_push", "execute_command"):
            with self.subTest(tool=tool):
                self.assertIn(tool, APPROVAL_REQUIRED)

    def test_read_only_operations_do_not_require_approval(self):
        executor = ToolExecutor()
        self.assertFalse(executor.requires_approval("status"))
