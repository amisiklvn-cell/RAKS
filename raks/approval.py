"""Approval gates for sensitive RAKS operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ApprovalRequest:
    operation: str
    reason: str
    target: str
    detail: str = ""


class ApprovalGate:
    def approve(self, request: ApprovalRequest) -> bool:
        raise NotImplementedError


class CLIApprovalGate(ApprovalGate):
    """Ask on the terminal. Nothing is executed without an explicit yes."""

    def approve(self, request: ApprovalRequest) -> bool:
        print("APPROVAL REQUIRED")
        print(f"  operation: {request.operation}")
        print(f"  reason:    {request.reason}")
        print(f"  target:    {request.target}")
        if request.detail:
            print(f"  detail:    {request.detail[:300]}")
        try:
            answer = input("Approve? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in ("y", "yes")


class DenyGate(ApprovalGate):
    """Used by interfaces that cannot safely prompt for approval."""

    def __init__(self, message: str = "Approval is not available from this interface.") -> None:
        self.message = message

    def approve(self, request: ApprovalRequest) -> bool:
        print(f"Denied: {self.message} ({request.operation})")
        return False


class AutoApproveGate(ApprovalGate):
    """For tests only. Never used by terminal or browser interfaces."""

    def approve(self, request: ApprovalRequest) -> bool:
        return True


def describe(request: ApprovalRequest) -> str:
    return f"{request.operation} on {request.target}: {request.reason}"
