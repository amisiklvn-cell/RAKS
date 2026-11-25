"""Development Command Center planning layer.

The interpreter classifies input, this module builds an explicit plan, and the
tool executor performs only approved, named operations. Natural-language text
is never turned into shell commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .tools import APPROVAL_REQUIRED

TASK_PLANS = {
    "status": ("Report system and workspace status", [("status", {})]),
    "history": ("Show recent memory history", [("git_log", {"limit": 5})]),
    "backup": ("Back up the approved workspace", [("backup", {})]),
    "scan": ("Run a defensive security inspection", [("security_scan", {})]),
    "tests": ("Run the test suite", [("run_tests", {})]),
    "compile": ("Compile Python sources", [("compile_python", {})]),
}


@dataclass(frozen=True)
class PlanStep:
    description: str
    tool: str
    requires_approval: bool
    arguments: Dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskPlan:
    summary: str
    steps: List[PlanStep] = field(default_factory=list)


@dataclass(frozen=True)
class ApprovalRequest:
    operation: str
    reason: str
    target: str


@dataclass(frozen=True)
class TaskResult:
    success: bool
    output: str
    error: Optional[str] = None


class DevelopmentCommandCenter:
    """Builds deterministic plans for trusted, named commands only."""

    def plan(self, intent: str) -> TaskPlan:
        key = (intent or "").strip().lower().lstrip("/")
        if key not in TASK_PLANS:
            raise NotImplementedError(f"no plan is defined for {intent!r}")
        summary, operations = TASK_PLANS[key]
        steps = [
            PlanStep(
                description=f"Execute {tool}",
                tool=tool,
                requires_approval=tool in APPROVAL_REQUIRED,
                arguments=dict(arguments),
            )
            for tool, arguments in operations
        ]
        return TaskPlan(summary=summary, steps=steps)

    def plans(self) -> List[str]:
        return sorted(TASK_PLANS)
