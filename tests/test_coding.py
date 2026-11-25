import tempfile
import unittest
from pathlib import Path

from raks.approval import AutoApproveGate
from raks.coding import CodingAgent, detect_language
from raks.tools import ToolExecutor


class CodingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.agent = CodingAgent(ToolExecutor({"workspaces": [self.tmp.name]}, AutoApproveGate()))

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_supported_languages_are_listed(self):
        languages = self.agent.languages()
        for name in ("python", "java", "javascript", "html", "css", "bash", "json", "xml", "android"):
            self.assertIn(name, languages)

    def test_scaffold_and_validate_python(self):
        target = self.root / "pyproj"
        result = self.agent.scaffold("python", str(target))
        self.assertTrue(result["success"], result)
        self.assertTrue((target / "main.py").is_file())
        report = self.agent.validate(str(target))
        self.assertTrue(report.ok, report.text)
        self.assertEqual(report.files_checked, 1)

    def test_scaffold_android_has_source_skeleton(self):
        target = self.root / "android"
        result = self.agent.scaffold("android", str(target))
        self.assertTrue(result["success"])
        self.assertIn("AndroidManifest.xml", result["files"])
        self.assertTrue((target / "app/src/main/java/com/example/raks/MainActivity.java").is_file())
        report = self.agent.validate(str(target))
        self.assertTrue(report.ok, report.text)

    def test_invalid_json_is_detected(self):
        path = self.root / "bad.json"
        path.write_text("{ invalid }", encoding="utf-8")
        report = self.agent.validate(str(path))
        self.assertFalse(report.ok)
        self.assertIn("invalid JSON", report.text)

    def test_invalid_xml_is_detected(self):
        path = self.root / "bad.xml"
        path.write_text("<a><b></a>", encoding="utf-8")
        report = self.agent.validate(str(path))
        self.assertFalse(report.ok)
        self.assertIn("invalid XML", report.text)

    def test_unsupported_language_is_honest(self):
        result = self.agent.scaffold("cobol", str(self.root / "x"))
        self.assertFalse(result["success"])
        self.assertIn("unsupported", result["error"])

    def test_detect_language(self):
        self.assertEqual(detect_language(Path("a.py")), "python")
        self.assertEqual(detect_language(Path("a.xyz")), "unknown")
