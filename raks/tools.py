"""Tool executor boundary.

No tool is executable in v0.1.0. This module contains no shell calls, file
writes, installs, builds, or Git operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

APPROVAL_REQUIRED = frozenset(
    {
        "write_file",
        "install",
        "build",
        "git_push",
        "execute_command",
    }
)


@dataclass(frozen=True)
class ToolResult:
    implemented: bool
    success: bool
    message: str


class ToolExecutor:
    def requires_approval(self, tool_name: str) -> bool:
        return tool_name in APPROVAL_REQUIRED

    def execute(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, object]] = None,
    ) -> ToolResult:
        return ToolResult(
            implemented=False,
            success=False,
            message=f"Tool '{tool_name}' is not implemented yet in v0.1.0.",
        )
