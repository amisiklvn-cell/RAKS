"""Automation and GitHub integration using only fixed, allowlisted commands.

No arbitrary shell strings are accepted. GitHub operations use the `gh` CLI
with explicit argument lists and never force-push.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from urllib.parse import quote
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import logger
from .tools import ToolExecutor


class IntegrationUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class RepoInfo:
    url: str
    default_branch: str
    private: bool
    size: int

    @property
    def text(self) -> str:
        return (
            f"Repository: {self.url}\n"
            f"Default branch: {self.default_branch}\n"
            f"Private: {self.private}\n"
            f"Size: {self.size}"
        )


class GitHubClient:
    """Read-only GitHub queries plus explicitly requested writes."""

    def __init__(self, repo: str = "amisiklvn-cell/RAKS") -> None:
        self.repo = repo
        self.cli = shutil.which("gh")

    def available(self) -> bool:
        return self.cli is not None

    def _run(self, arguments: List[str], timeout: int = 60) -> str:
        if not self.available():
            raise IntegrationUnavailable("GitHub CLI is not installed")
        command = [self.cli or "gh", *arguments]
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise IntegrationUnavailable(f"gh failed to start: {exc}") from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip().splitlines()[-1:] or ["unknown error"]
            raise IntegrationUnavailable(f"gh exited {completed.returncode}: {detail[0]}")
        return completed.stdout.strip()

    def repo_info(self, cwd: Optional[str] = None) -> RepoInfo:
        raw = self._run(
            ["api", f"repos/{self.repo}", "--jq",
             "{url: .html_url, default_branch, private, size}"]
        )
        data = json.loads(raw)
        return RepoInfo(
            url=data.get("url", ""),
            default_branch=data.get("default_branch", "main"),
            private=bool(data.get("private", False)),
            size=int(data.get("size", 0)),
        )

    def commits(self, branch: str = "main", limit: int = 5) -> List[str]:
        query = f"sha={quote(branch, safe='')}&per_page={max(1, min(int(limit), 100))}"
        raw = self._run(
            ["api", f"repos/{self.repo}/commits?{query}", "--jq",
             '.[] | .sha + " " + (.commit.message | split("\\n")[0])']
        )
        return raw.splitlines()

    def remote_head(self, branch: str = "main") -> str:
        return self._run(
            ["api", f"repos/{self.repo}/commits/{branch}", "--jq", ".sha"]
        )

    def create_issue(self, title: str, body: str) -> str:
        if not title.strip():
            raise IntegrationUnavailable("issue title is required")
        logger.log("github_issue_create")
        return self._run(
            ["issue", "create", "--repo", self.repo, "--title", title[:200], "--body", body[:4000]]
        )


AUTOMATIONS: Dict[str, List[Dict[str, Any]]] = {
    "check": [
        {"tool": "status"},
        {"tool": "git_status"},
        {"tool": "security_scan"},
    ],
    "verify": [
        {"tool": "compile_python"},
        {"tool": "run_tests"},
    ],
    "snapshot": [
        {"tool": "backup"},
        {"tool": "git_status"},
    ],
}


class AutomationCenter:
    def __init__(self, tools: ToolExecutor) -> None:
        self.tools = tools
        self.github = GitHubClient()

    def names(self) -> List[str]:
        return sorted(AUTOMATIONS)

    def run(self, name: str) -> List[Dict[str, Any]]:
        key = (name or "").strip().lower()
        if key not in AUTOMATIONS:
            raise NotImplementedError(f"unknown automation: {name}")
        results = []
        for step in AUTOMATIONS[key]:
            result = self.tools.execute(step["tool"], step.get("arguments", {}))
            results.append({
                "tool": step["tool"],
                "success": result.success,
                "message": result.message,
            })
        return results
