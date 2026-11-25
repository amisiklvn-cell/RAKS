"""Terminal rendering for RAKS.

Colors are emitted only when stdout is a TTY. This keeps logs and tests clean.
"""

from __future__ import annotations

import sys
from typing import Dict, Iterable, Optional, TextIO, Tuple

from .config import APP_NAME, APP_NAME_SHORT, MENU_ITEMS, PROJECT_URL, VERSION

LOGO = (
    "  ____   ____   ___   ____ ",
    " |  _ \\ |  _ \\ / _ \\ |  _ \\ ",
    " | |_) || |_) || | | || |_) |",
    " |  _ < |  _ < | |_| ||  _ < ",
    " |_| \\_\\|_| \\_\\ \\___/ |_| \\_\\",
)

STATUS_FIELDS = (
    ("platform", "Platform"),
    ("architecture", "Architecture"),
    ("python", "Python"),
    ("ram_total", "RAM total"),
    ("ram_available", "RAM available"),
    ("storage_free", "Storage free"),
    ("git", "Git"),
    ("gh", "GitHub CLI"),
    ("ai_engine", "AI engine"),
    ("mode", "Mode"),
)


class TerminalUI:
    RESET = "\033[0m"
    BACKGROUND = "\033[40m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    DIM = "\033[2m"
    BOLD = "\033[1m"

    def __init__(self, stream: Optional[TextIO] = None) -> None:
        self.stream: TextIO = stream if stream is not None else sys.stdout
        self.colors = bool(getattr(self.stream, "isatty", lambda: False)())

    def _write(self, text: str = "", codes: Iterable[str] = ()) -> None:
        if self.colors:
            style = "".join(codes)
            self.stream.write(f"{self.BACKGROUND}{style}{text}{self.RESET}\n")
        else:
            self.stream.write(f"{text}\n")
        self.stream.flush()

    def newline(self) -> None:
        self.stream.write("\n")
        self.stream.flush()

    def banner(self, status: Dict[str, str]) -> None:
        self.newline()
        for index, line in enumerate(LOGO):
            self._write(line, (self.RED if index % 2 == 0 else self.CYAN,))
        self._write(f"  {APP_NAME}  v{VERSION}", (self.BOLD, self.CYAN))
        self._write(f"  {PROJECT_URL}", (self.DIM,))
        self.newline()
        self.status_report(status, heading="SYSTEM STATUS")
        self.newline()

    def status_report(self, status: Dict[str, str], heading: str = "STATUS") -> None:
        self._write(heading, (self.BOLD, self.RED))
        for key, label in STATUS_FIELDS:
            self._write(f"  {label:<14}: {status.get(key, 'unknown')}", (self.CYAN,))

    def dashboard(self) -> None:
        self._write("MAIN MENU", (self.BOLD, self.RED))
        for number, name in enumerate(MENU_ITEMS, start=1):
            self._write(f"  {number:>2}. {name}", (self.CYAN,))
        self._write("Enter a number, or type /help for commands.", (self.DIM,))

    def section(self, title: str) -> None:
        self.newline()
        self._write(title, (self.BOLD, self.RED))

    def help(self) -> None:
        self._write("COMMANDS", (self.BOLD, self.RED))
        self._write("  /help       show this help", (self.CYAN,))
        self._write("  /status     show system status", (self.CYAN,))
        self._write("  /clear      clear the screen", (self.CYAN,))
        self._write("  /menu       show the main menu", (self.CYAN,))
        self._write("  /exit       leave RAKS", (self.CYAN,))
        self._write("  /web        start|stop|status browser interface", (self.CYAN,))
        self._write("  /tools      list approved tools", (self.CYAN,))
        self._write("  /history    show recent conversation", (self.CYAN,))
        self._write("  /backup     back up the workspace", (self.CYAN,))
        self._write("  /restore    restore a backup archive", (self.CYAN,))
        self._write("  /security   run defensive scan", (self.CYAN,))
        self._write("  /code       scaffold|validate|languages", (self.CYAN,))
        self._write("  /automate   run an automation", (self.CYAN,))
        self._write("  /github     show repository status", (self.CYAN,))
        self._write("  /config     show or set a setting", (self.CYAN,))
        self._write("  /ops        log|stats", (self.CYAN,))
        self._write("  1-10        open a menu section", (self.CYAN,))
        self._write("  text        send a request to the AI engine", (self.DIM,))

    def info(self, message: str) -> None:
        self._write(f"  {message}", (self.DIM,))

    def not_implemented(self, feature: str) -> None:
        self._write(f"{feature}: not implemented yet in v{VERSION}.", (self.RED,))

    def error(self, message: str) -> None:
        self._write(f"error: {message}", (self.RED,))

    def clear(self) -> None:
        if self.colors:
            self.stream.write("\033[2J\033[H")
        self.stream.write("Screen cleared.\n")
        self.stream.flush()

    def prompt(self) -> str:
        if self.colors:
            self.stream.write(f"{self.BACKGROUND}{self.CYAN}raks > {self.RESET}")
        else:
            self.stream.write("raks > ")
        self.stream.flush()
        return input()

    def goodbye(self) -> None:
        self._write(f"{APP_NAME_SHORT} stopped. Goodbye.", (self.CYAN,))
