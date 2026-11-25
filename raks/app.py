"""RAKS terminal application loop (Stage 1)."""

from __future__ import annotations

from typing import Dict, Optional, TextIO

from . import commands, config, engine, logger, memory, planner, system, tools
from .config import load_settings
from .ui import TerminalUI

MENU_NAMES = {str(number): name for number, name in enumerate(config.MENU_ITEMS, start=1)}


class RaksApp:
    def __init__(self, stream: Optional[TextIO] = None) -> None:
        self.ui = TerminalUI(stream)
        self.interpreter = commands.CommandInterpreter()
        self.settings = load_settings()
        self.engine = engine.HybridAIEngine(self.settings)
        self.tools = tools.ToolExecutor()
        self.command_center = planner.DevelopmentCommandCenter()
        self.memory = memory.MemoryStore()
        self.status: Dict[str, str] = system.collect_system_status()

    def run(self) -> None:
        self.ui.banner(self.status)
        self.ui.dashboard()
        logger.log("startup", version=config.VERSION, platform=self.status.get("platform", ""))

        while True:
            try:
                raw = self.ui.prompt()
            except (EOFError, KeyboardInterrupt):
                self.ui.newline()
                break
            result = self.interpreter.parse(raw)
            logger.log("command", action=result.action)
            if not self.dispatch(result):
                break

        self.ui.goodbye()
        logger.log("shutdown", version=config.VERSION)

    def dispatch(self, result: commands.CommandResult) -> bool:
        """Handle one classified command. Return False to stop the loop."""
        action = result.action
        value = result.value or ""

        if action == "exit":
            return False
        if action == "empty":
            return True
        if action == "help":
            self.ui.help()
            return True
        if action == "status":
            self.ui.status_report(self.status)
            return True
        if action == "clear":
            self.ui.clear()
            return True
        if action == "menu":
            self.ui.dashboard()
            return True
        if action == "unknown_command":
            self.ui.error(f"unknown command {value!r}; type /help")
            return True
        if action == "invalid_menu":
            self.ui.error(f"{value!r} is not a menu option (1-10)")
            return True
        if action == "menu_item":
            self._menu_item(value)
            return True
        if action == "chat":
            self._chat(value)
            return True

        self.ui.error(f"unhandled command action {action!r}")
        return True

    def _chat(self, prompt: str) -> None:
        response = self.engine.respond(prompt)
        if not response.available:
            self.ui.error(response.text)
            return
        self.ui.info(f"[{response.route}/{response.provider}] {response.text}")

    def _menu_item(self, number: str) -> None:
        name = MENU_NAMES[number]
        if number == "1":
            self._chat("menu request")
            return
        if number == "9":
            self.ui.status_report(self.status)
            self.ui.not_implemented("Full System Monitor")
            return
        if number == "10":
            self.ui.info(
                f"Settings are read-only in v{config.VERSION}. "
                f"Approved workspace: {config.WORKSPACE_ROOT}"
            )
            self.ui.not_implemented("Editable Settings")
            return
        self.ui.not_implemented(name)


def main() -> int:
    RaksApp().run()
    return 0
