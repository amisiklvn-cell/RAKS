import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from raks import logger

SECRETS = (
    "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
    "sk-abcdefghijklmnopqrstuvwxyz1234567890",
    "AKIAIOSFODNN7EXAMPLE",
    "Bearer ghp_abcdefghijklmnopqrstuvwxyz1234567890",
    "SENTINEL_PRIVATE_CONVERSATION_TEXT",
)


class LoggerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "raks.log"
        self.patch = patch.object(logger, "LOG_FILE", self.log)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_sensitive_fields_are_discarded(self):
        logger.log(
            "chat",
            prompt=SECRETS[4],
            content=SECRETS[4],
            token=SECRETS[0],
            authorization=SECRETS[3],
            path="/api/chat?token=" + SECRETS[0],
            title=SECRETS[4],
            route="online",
        )
        record = json.loads(self.log.read_text(encoding="utf-8").strip())
        self.assertEqual(set(record) - {"time", "event"}, {"route"})
        for secret in SECRETS:
            self.assertNotIn(secret, self.log.read_text(encoding="utf-8"))

    def test_secret_values_in_safe_fields_are_redacted(self):
        logger.log("tool_executed", tool=SECRETS[0])
        text = self.log.read_text(encoding="utf-8")
        self.assertNotIn(SECRETS[0], text)
        self.assertIn("[REDACTED]", text)

    def test_web_path_is_not_logged(self):
        with patch("raks.web.logger.log") as spy:
            from raks.web import ENDPOINTS

            self.assertEqual(ENDPOINTS["/api/chat"], "chat")
        logger.log("web_request", method="POST", endpoint="chat", path="/api/chat?key=" + SECRETS[0])
        record = json.loads(self.log.read_text(encoding="utf-8").strip())
        self.assertNotIn("path", record)
        self.assertNotIn(SECRETS[0], self.log.read_text(encoding="utf-8"))

    def test_every_production_log_call_uses_allowlisted_fields(self):
        package = Path(__file__).resolve().parent.parent / "raks"
        violations = []
        for source in sorted(package.glob("*.py")):
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                if not (
                    isinstance(function, ast.Attribute)
                    and function.attr == "log"
                    and isinstance(function.value, ast.Name)
                    and function.value.id == "logger"
                ):
                    continue
                for keyword in node.keywords:
                    name = keyword.arg or "**kwargs"
                    if name not in logger.SAFE_FIELDS:
                        violations.append((source.name, node.lineno, name))
        self.assertEqual(violations, [], f"unsafe logger fields: {violations}")

    def test_sanitize_existing_log_rewrites_old_records(self):
        old = "\n".join(
            [
                json.dumps({"time": "t", "event": "chat", "prompt": SECRETS[4]}),
                json.dumps({"time": "t", "event": "web_request", "path": "/?token=" + SECRETS[0]}),
                "not-json",
            ]
        ) + "\n"
        self.log.write_text(old, encoding="utf-8")
        kept = logger.sanitize_existing_log(str(self.log))
        self.assertEqual(kept, 2)
        text = self.log.read_text(encoding="utf-8")
        for secret in SECRETS:
            self.assertNotIn(secret, text)
        self.assertNotIn("not-json", text)
        for line in text.splitlines():
            self.assertLessEqual(set(json.loads(line)) - {"time", "event"}, set(logger.SAFE_FIELDS))
