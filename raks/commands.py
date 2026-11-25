"""Command interpreter for RAKS.

This module only classifies text into actions. It never executes commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SLASH_COMMANDS = {
    "/help": "help",
    "/status": "status",
    "/clear": "clear",
    "/menu": "menu",
    "/exit": "exit",
    "/web": "web",
    "/tools": "tools",
    "/history": "history",
    "/backup": "backup",
    "/restore": "restore",
    "/security": "security",
    "/code": "code",
    "/automate": "automate",
    "/github": "github",
    "/config": "config",
    "/ops": "ops",
    "/conversation": "conversation",
    "/plan": "plan",
    "/project": "project",
}


@dataclass(frozen=True)
class CommandResult:
    action: str
    value: Optional[str] = None


class CommandInterpreter:
    def parse(self, raw: str) -> CommandResult:
        text = raw.strip()
        if not text:
            return CommandResult("empty")

        if text.startswith("/"):
            parts = text.split(None, 1)
            token = parts[0].lower()
            argument = parts[1].strip() if len(parts) > 1 else None
            action = SLASH_COMMANDS.get(token)
            if action is None:
                return CommandResult("unknown_command", token)
            return CommandResult(action, argument)

        if text.isdigit():
            number = int(text)
            if 1 <= number <= 10:
                return CommandResult("menu_item", str(number))
            return CommandResult("invalid_menu", text)

        return CommandResult("chat", text)
