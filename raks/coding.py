"""Coding agent: scaffolding and static validation, not simulated intelligence.

Supported languages: Python, Java, JavaScript, HTML, CSS, Bash, JSON, XML and
Android project skeletons. Validation uses only the Python standard library.
"""

from __future__ import annotations

import json
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .tools import ToolExecutor

LANGUAGES = {
    "python": ".py",
    "java": ".java",
    "javascript": ".js",
    "html": ".html",
    "css": ".css",
    "bash": ".sh",
    "json": ".json",
    "xml": ".xml",
    "android": ".java",
}

TEMPLATES: Dict[str, Dict[str, str]] = {
    "python": {"main.py": "#!/usr/bin/env python3\n\"\"\"RAKS Python starter.\"\"\"\n\n\ndef main() -> None:\n    print(\"Hello from RAKS\")\n\n\nif __name__ == \"__main__\":\n    main()\n"},
    "java": {"Main.java": "public class Main {\n    public static void main(String[] args) {\n        System.out.println(\"Hello from RAKS\");\n    }\n}\n"},
    "javascript": {"main.js": "// RAKS JavaScript starter\nfunction greet(name) {\n  return `Hello, ${name} from RAKS`;\n}\nconsole.log(greet('world'));\n"},
    "html": {"index.html": "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<title>RAKS</title>\n</head>\n<body>\n<h1>Hello from RAKS</h1>\n</body>\n</html>\n"},
    "css": {"style.css": "/* RAKS CSS starter */\nbody {\n  margin: 0;\n  font-family: monospace;\n}\n"},
    "bash": {"main.sh": "#!/usr/bin/env bash\nset -euo pipefail\n# RAKS Bash starter\necho \"Hello from RAKS\"\n"},
    "json": {"config.json": "{\n  \"name\": \"raks\",\n  \"version\": \"1.0.0\"\n}\n"},
    "xml": {"data.xml": "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<raks>\n  <message>Hello from RAKS</message>\n</raks>\n"},
    "android": {
        "AndroidManifest.xml": "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<manifest xmlns:android=\"http://schemas.android.com/apk/res/android\" package=\"com.example.raks\">\n    <application android:label=\"RAKS\">\n        <activity android:name=\".MainActivity\" android:exported=\"true\">\n            <intent-filter>\n                <action android:name=\"android.intent.action.MAIN\" />\n                <category android:name=\"android.intent.category.LAUNCHER\" />\n            </intent-filter>\n        </activity>\n    </application>\n</manifest>\n",
        "app/src/main/java/com/example/raks/MainActivity.java": "package com.example.raks;\n\nimport android.app.Activity;\nimport android.os.Bundle;\n\npublic class MainActivity extends Activity {\n    @Override\n    protected void onCreate(Bundle savedInstanceState) {\n        super.onCreate(savedInstanceState);\n    }\n}\n",
        "app/src/main/res/layout/activity_main.xml": "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<LinearLayout xmlns:android=\"http://schemas.android.com/apk/res/android\"\n    android:layout_width=\"match_parent\"\n    android:layout_height=\"match_parent\"\n    android:orientation=\"vertical\" />\n",
        "README.md": "# Android starter\n\nThis is a source skeleton only. Building requires an Android SDK and Gradle,\nwhich are not included in RAKS.\n",
    },
}


@dataclass
class ValidationIssue:
    path: str
    message: str


@dataclass
class ValidationReport:
    language: str
    files_checked: int = 0
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def text(self) -> str:
        lines = [f"VALIDATION ({self.language})", f"Files checked: {self.files_checked}"]
        if self.ok:
            lines.append("No static issues found.")
        for issue in self.issues:
            lines.append(f"  {issue.path}: {issue.message}")
        return "\n".join(lines)


def detect_language(path: Path) -> str:
    suffixes = {
        ".py": "python", ".java": "java", ".js": "javascript", ".html": "html",
        ".css": "css", ".sh": "bash", ".json": "json", ".xml": "xml",
    }
    for suffix, language in suffixes.items():
        if path.name.endswith(suffix):
            return language
    return "unknown"


class CodingAgent:
    def __init__(self, tools: ToolExecutor) -> None:
        self.tools = tools

    def languages(self) -> List[str]:
        return sorted(LANGUAGES)

    def scaffold(self, language: str, target_dir: str) -> Dict[str, Any]:
        """Create a starter project through the approval-controlled executor."""
        language = language.strip().lower()
        if language not in TEMPLATES:
            return {"success": False, "error": f"unsupported language: {language}"}
        created: List[str] = []
        for name, content in TEMPLATES[language].items():
            result = self.tools.execute(
                "write_file",
                {"path": str(Path(target_dir) / name), "content": content},
            )
            if not result.success:
                return {"success": False, "error": result.message, "created": created}
            created.append(name)
        return {"success": True, "language": language, "files": created}

    def validate(self, path: str) -> ValidationReport:
        """Static validation of a file or directory."""
        target = Path(path).expanduser().resolve()
        language = detect_language(target)
        files: List[Path] = []
        if target.is_file():
            files = [target]
        elif target.is_dir():
            files = sorted(
                item for item in target.rglob("*")
                if item.is_file() and detect_language(item) != "unknown"
                and ".git" not in item.parts
            )
        report = ValidationReport(language=language if target.is_file() else "mixed")
        report.files_checked = len(files)
        for item in files:
            self._validate_file(item, report)
        return report

    def _validate_file(self, path: Path, report: ValidationReport) -> None:
        language = detect_language(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = str(path)
        if language == "python":
            import py_compile
            with tempfile.TemporaryDirectory() as tmp:
                cache = Path(tmp) / "cache"
                try:
                    py_compile.compile(str(path), cfile=str(cache / (path.stem + ".pyc")), doraise=True)
                except Exception as exc:
                    report.issues.append(ValidationIssue(relative, str(exc)))
        elif language == "json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                report.issues.append(ValidationIssue(relative, f"invalid JSON: {exc}"))
        elif language in ("xml", "android"):
            try:
                ET.fromstring(text)
            except ET.ParseError as exc:
                report.issues.append(ValidationIssue(relative, f"invalid XML: {exc}"))
        elif language in ("javascript", "java", "css"):
            for opening, closing in (("{", "}"), ("(", ")"), ("[", "]")):
                if text.count(opening) != text.count(closing):
                    report.issues.append(
                        ValidationIssue(relative, f"unbalanced {opening}{closing}")
                    )
                    break
            if language == "javascript" and not re.search(r"\b(function|const|let|var)\b", text):
                report.issues.append(ValidationIssue(relative, "no JavaScript declarations found"))
        elif language == "bash":
            if not text.lstrip().startswith("#!"):
                report.issues.append(ValidationIssue(relative, "missing shebang"))
