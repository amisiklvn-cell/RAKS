"""Defensive-only security inspection for authorized workspaces.

This module NEVER exploits, attacks, or modifies targets. It only reads files
inside an approved workspace and produces a report. No network scanning and no
payload generation are performed.
"""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

SECRET_PATTERNS = {
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}

SENSITIVE_NAMES = re.compile(
    r"(\.env$|\.pem$|\.key$|credentials|secrets?|id_rsa|\.sqlite$|\.db$|\.log$)",
    re.IGNORECASE,
)

SKIP_DIRS = {".git", "__pycache__", "node_modules", "backups"}


@dataclass
class SecurityReport:
    root: str
    files_scanned: int = 0
    findings: List[Dict[str, str]] = field(default_factory=list)
    summary: str = ""

    @property
    def text(self) -> str:
        lines = [
            "DEFENSIVE SECURITY REPORT",
            f"Target: {self.root}",
            f"Files scanned: {self.files_scanned}",
            f"Findings: {len(self.findings)}",
            "",
        ]
        if not self.findings:
            lines.append("No defensive issues detected in the scanned workspace.")
        for item in self.findings:
            lines.append(f"[{item['severity']}] {item['kind']}: {item['path']} - {item['detail']}")
        lines.append("")
        lines.append("This report is inspection only. No files were changed.")
        return "\n".join(lines)


class SecurityScanner:
    """Read-only scanner restricted to an explicitly approved path."""

    def __init__(self, root: str) -> None:
        self.root = Path(root).expanduser().resolve()

    def scan(self, max_bytes: int = 2_000_000) -> SecurityReport:
        report = SecurityReport(root=str(self.root))
        if not self.root.is_dir():
            report.summary = "target is not a directory"
            return report

        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(self.root).parts):
                continue
            report.files_scanned += 1
            relative = str(path.relative_to(self.root))

            if SENSITIVE_NAMES.search(path.name):
                report.findings.append({
                    "kind": "sensitive_filename",
                    "severity": "info",
                    "path": relative,
                    "detail": "filename suggests credentials or private data",
                })

            mode = path.stat().st_mode
            if mode & stat.S_IWOTH:
                report.findings.append({
                    "kind": "world_writable",
                    "severity": "warning",
                    "path": relative,
                    "detail": "file is writable by other users",
                })

            if path.stat().st_size > max_bytes:
                report.findings.append({
                    "kind": "large_file",
                    "severity": "info",
                    "path": relative,
                    "detail": "file skipped from content scan (too large)",
                })
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for kind, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    report.findings.append({
                        "kind": "possible_secret",
                        "severity": "critical",
                        "path": relative,
                        "detail": f"pattern looks like {kind}; review and rotate if real",
                    })

        critical = sum(1 for item in report.findings if item["severity"] == "critical")
        report.summary = (
            f"scanned {report.files_scanned} files; "
            f"{len(report.findings)} findings ({critical} critical)"
        )
        return report


def scan_workspace(path: str) -> SecurityReport:
    return SecurityScanner(path).scan()
