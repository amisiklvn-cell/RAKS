import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from raks.approval import DenyGate
from tests import AutoGate
from raks.automation import AutomationCenter, GitHubClient, IntegrationUnavailable
from raks.planner import DevelopmentCommandCenter
from raks.tools import ToolExecutor


class PlannerTests(unittest.TestCase):
    def test_known_intent_builds_plan(self):
        plan = DevelopmentCommandCenter().plan("backup")
        self.assertIn("workspace", plan.summary.lower())
        self.assertEqual(plan.steps[0].tool, "backup")
        self.assertTrue(plan.steps[0].requires_approval)

    def test_unknown_intent_refuses(self):
        with self.assertRaises(NotImplementedError):
            DevelopmentCommandCenter().plan("rm -rf /")


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        subprocess.run(["git", "init", "-q", self.tmp.name], check=False, capture_output=True)
        self.tools = ToolExecutor({"workspaces": [self.tmp.name]}, AutoGate())

    def tearDown(self):
        self.tmp.cleanup()

    def test_known_automation_runs(self):
        center = AutomationCenter(self.tools)
        self.assertIn("verify", center.names())
        results = center.run("check")
        self.assertEqual(len(results), 3)
        self.assertTrue(all(item["success"] for item in results), results)

    def test_unknown_automation_refuses(self):
        with self.assertRaises(NotImplementedError):
            AutomationCenter(self.tools).run("delete everything")


class GitHubTests(unittest.TestCase):
    def test_repo_info_parses_response(self):
        client = GitHubClient()
        completed = subprocess.CompletedProcess(
            [], 0, '{"url":"https://github.com/amisiklvn-cell/RAKS",'
                  '"default_branch":"main","private":false,"size":0}', ""
        )
        with patch("raks.automation.shutil.which", return_value="gh"), \
             patch("raks.automation.subprocess.run", return_value=completed):
            info = client.repo_info()
        self.assertEqual(info.default_branch, "main")
        self.assertIn("RAKS", info.text)

    def test_missing_cli_reports_unavailable(self):
        with patch("raks.automation.shutil.which", return_value=None):
            client = GitHubClient()
            self.assertFalse(client.available())
            with self.assertRaises(IntegrationUnavailable):
                client.remote_head()

    def test_no_force_push_command_exists(self):
        source = (Path(__file__).parent.parent / "raks" / "automation.py").read_text(encoding="utf-8")
        self.assertNotIn("--force", source)
        self.assertNotIn("--force-with-lease", source)
