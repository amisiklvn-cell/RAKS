"""RAKS terminal application loop backed by the shared application core."""

from __future__ import annotations

from typing import Any, Dict, Optional, TextIO

from . import commands, config, logger, planner, system
from .automation import AutomationCenter, GitHubClient, IntegrationUnavailable
from .coding import CodingAgent
from .config import load_settings
from .core import RAKSCore
from .ops import OperationsCenter
from .tools import ToolResult
from .ui import TerminalUI
from .web import WebServer

MENU_NAMES = {str(number): name for number, name in enumerate(config.MENU_ITEMS, start=1)}


class RaksApp:
    def __init__(
        self,
        stream: Optional[TextIO] = None,
        core: Optional[RAKSCore] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.ui = TerminalUI(stream)
        self.interpreter = commands.CommandInterpreter()
        self.settings = settings if settings is not None else load_settings()
        self.core = core if core is not None else RAKSCore(self.settings)
        self.engine = self.core.engine
        self.tools = self.core.tools
        self.memory = self.core.memory
        self.command_center = planner.DevelopmentCommandCenter()
        self.coding = CodingAgent(self.tools)
        self.automation = AutomationCenter(self.tools)
        self.ops = OperationsCenter(self.tools)
        self.github = GitHubClient()
        self.web: Optional[WebServer] = None
        self.status: Dict[str, str] = system.collect_system_status()
        engine_status = self.engine.status()
        self.status["ai_engine"] = engine_status.get("mode", "hybrid")
        self.status["mode"] = "offline-first"

    def run(self) -> None:
        self.ui.banner(self.status)
        self.ui.dashboard()
        logger.log("startup", version=config.VERSION, platform=self.status.get("platform", ""))
        try:
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
        finally:
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
        elif action == "status":
            self.ui.status_report(self.status)
        elif action == "clear":
            self.ui.clear()
        elif action == "menu":
            self.ui.dashboard()
        elif action == "unknown_command":
            self.ui.error(f"unknown command {value!r}; type /help")
        elif action == "invalid_menu":
            self.ui.error(f"{value!r} is not a menu option (1-10)")
        elif action == "menu_item":
            self._menu_item(value)
        elif action == "chat":
            self._chat(value)
        elif action == "web":
            self._web(value)
        elif action == "tools":
            self._tools()
        elif action == "history":
            self._history()
        elif action == "backup":
            self._backup()
        elif action == "restore":
            self._restore(value)
        elif action == "security":
            self._security()
        elif action == "code":
            self._code(value)
        elif action == "automate":
            self._automate(value)
        elif action == "github":
            self._github()
        elif action == "config":
            self._config(value)
        elif action == "ops":
            self._ops(value)
        elif action == "conversation":
            self._conversation(value)
        elif action == "plan":
            self._plan(value)
        elif action == "project":
            self._project(value)
        else:
            self.ui.error(f"unhandled command action {action!r}")
        return True

    # ---- AI and shared core ---------------------------------------------
    def _chat(self, prompt: str) -> None:
        response = self.core.chat(prompt)
        if not response.get("available"):
            self.ui.error(response["text"])
            return
        self.ui.info(
            f"[{response['route']}/{response['provider']}] {response['text']}"
        )

    def _history(self) -> None:
        rows = self.core.history(20)
        self.ui.section("RECENT HISTORY")
        if not rows:
            self.ui.info("No conversation history yet.")
        for row in rows:
            self.ui.info(f"{row['role']}: {row['content'][:200]}")
        self.ui.info(f"memory stats: {self.memory.stats()}")

    # ---- tools, coding, automation --------------------------------------
    def _show_result(self, result: ToolResult) -> None:
        if result.success:
            self.ui.info(result.message)
            if result.data.get("output"):
                for line in str(result.data["output"]).splitlines()[:40]:
                    self.ui.info(line)
        else:
            self.ui.error(result.message)

    def _tools(self) -> None:
        self.ui.section("APPROVED TOOLS")
        for name in self.core.tool_names():
            flag = "approval required" if self.tools.requires_approval(name) else "read-only"
            self.ui.info(f"{name:<18} {flag}")
        self._show_result(self.tools.execute("status"))

    def _code(self, value: str) -> None:
        parts = value.split()
        if not parts or parts[0] == "languages":
            self.ui.section("CODING LANGUAGES")
            self.ui.info(", ".join(self.coding.languages()))
            return
        operation = parts[0].lower()
        if operation == "validate" and len(parts) >= 2:
            report = self.coding.validate(" ".join(parts[1:]))
            self.ui.section("VALIDATION")
            for line in report.text.splitlines():
                self.ui.info(line)
            return
        if operation == "scaffold" and len(parts) >= 3:
            result = self.coding.scaffold(parts[1].lower(), " ".join(parts[2:]))
            self.ui.section("SCAFFOLD")
            if result["success"]:
                self.ui.info(f"created: {', '.join(result['files'])}")
            else:
                self.ui.error(result.get("error", "scaffold failed"))
            return
        self.ui.error("usage: /code languages | /code validate PATH | /code scaffold LANG DIR")

    def _automate(self, value: str) -> None:
        if not value:
            self.ui.section("AUTOMATIONS")
            self.ui.info(", ".join(self.automation.names()))
            return
        try:
            results = self.automation.run(value)
        except NotImplementedError as exc:
            self.ui.error(str(exc))
            return
        self.ui.section(f"AUTOMATION: {value}")
        for item in results:
            status = "ok" if item["success"] else "failed"
            self.ui.info(f"{item['tool']}: {status} - {item['message'][:160]}")

    # ---- security, GitHub, backups, settings ----------------------------
    def _security(self) -> None:
        result = self.tools.execute("security_scan")
        self.ui.section("DEFENSIVE SECURITY")
        if result.success:
            for line in str(result.data.get("report", "")).splitlines()[:60]:
                self.ui.info(line)
        else:
            self.ui.error(result.message)

    def _github(self) -> None:
        self.ui.section("GITHUB")
        try:
            self.ui.info(self.github.repo_info().text.replace("\n", " | "))
            self.ui.info("recent commits:")
            for line in self.github.commits(limit=5):
                self.ui.info(line[:100])
        except IntegrationUnavailable as exc:
            self.ui.error(str(exc))

    def _backup(self) -> None:
        result = self.ops.backup()
        self.ui.section("BACKUP")
        self.ui.info(result.message)
        if result.success and result.data.get("archive"):
            self.ui.info(f"archive: {result.data['archive']}")

    def _restore(self, value: str) -> None:
        if not value:
            listed = self.ops.list_backups()
            self.ui.section("BACKUPS")
            for item in listed.data.get("backups", []):
                self.ui.info(f"{item['name']} ({item['size']} bytes)")
            if not listed.data.get("backups"):
                self.ui.info("No backups found.")
            return
        result = self.ops.restore(value)
        self.ui.section("RESTORE")
        self.ui.info(result.message)

    def _config(self, value: str = "") -> None:
        parts = value.split(None, 1)
        if not parts:
            current = self.ops.config()
            self.ui.section("SETTINGS")
            for key, item in sorted(current.data["settings"].items()):
                self.ui.info(f"{key} = {item}")
            return
        if len(parts) == 2:
            result = self.ops.set_config(parts[0], parts[1])
            self.ui.info(result.message)
            return
        self.ui.error("usage: /config KEY VALUE")

    def _ops(self, value: str) -> None:
        operation = (value or "log").lower()
        if operation == "stats":
            result = self.ops.log_stats()
            self.ui.section("LOG STATS")
            self.ui.info(result.message)
            for key, count in sorted(result.data["events"].items()):
                self.ui.info(f"{key}: {count}")
        else:
            result = self.ops.log_tail()
            self.ui.section("RECENT LOG ENTRIES")
            for line in result.data["lines"]:
                self.ui.info(line[:160])

    def _conversation(self, value: str) -> None:
        parts = value.split(None, 1)
        operation = (parts[0].lower() if parts else "list")
        if operation in ("list", ""):
            self.ui.section("CONVERSATIONS")
            rows = self.core.conversations()
            if not rows:
                self.ui.info("No conversations found.")
            for row in rows:
                flag = "active" if row["active"] else "saved"
                self.ui.info(f"{row['id']}  {row['title']}  ({row['messages']} messages, {flag})")
            return
        if operation == "new" and len(parts) == 2:
            conversation_id = self.core.new_conversation(parts[1].strip() or "default")
            self.ui.info(f"created conversation {conversation_id}")
            return
        if operation == "switch" and len(parts) == 2:
            ok = self.core.switch_conversation(parts[1].strip())
            self.ui.info("switched conversation" if ok else "conversation not found")
            return
        self.ui.error("usage: /conversation list | new TITLE | switch ID")

    def _plan(self, value: str) -> None:
        parts = value.split(None, 1)
        if not parts or not parts[0]:
            self.ui.section("PLANNED INTENTS")
            self.ui.info(", ".join(self.command_center.plans()))
            return
        intent = parts[0].lower()
        execute = intent == "run"
        if execute:
            if len(parts) != 2:
                self.ui.error("usage: /plan run INTENT")
                return
            intent = parts[1].lower()
        try:
            plan = self.command_center.plan(intent)
        except NotImplementedError as exc:
            self.ui.error(str(exc))
            return
        self.ui.section(f"PLAN: {plan.summary}")
        for step in plan.steps:
            flag = "approval" if step.requires_approval else "read-only"
            self.ui.info(f"{step.description} | tool={step.tool} | {flag}")
        if execute:
            for step in plan.steps:
                self._show_result(self.tools.execute(step.tool, step.arguments))

    def _project(self, value: str) -> None:
        parts = value.split(None, 2)
        operation = (parts[0].lower() if parts else "list")
        if operation in ("list", ""):
            self.ui.section("PROJECTS")
            projects = self.memory.recent_projects()
            if not projects:
                self.ui.info("No projects recorded yet.")
            for row in projects:
                self.ui.info(f"{row['name']}: {row['path']} ({row['created_at']})")
            self.ui.section("TASKS")
            tasks = self.memory.recent_tasks(10)
            if not tasks:
                self.ui.info("No tasks recorded yet.")
            for row in tasks:
                self.ui.info(f"[{row['status']}] {row['summary']}")
            return
        if operation == "add" and len(parts) >= 3:
            stored = self.memory.record_project(parts[1], " ".join(parts[2:]))
            self.ui.info("project recorded" if stored else "memory is disabled")
            return
        if operation == "task" and len(parts) >= 2:
            stored = self.memory.record_task(" ".join(parts[1:]), "open")
            self.ui.info("task recorded" if stored else "memory is disabled")
            return
        self.ui.error("usage: /project list | add NAME PATH | task SUMMARY")

    def _web(self, value: str) -> None:
        operation = (value or "status").lower()
        if operation == "start":
            if self.web is None:
                host = str(self.settings.get("web_host", "127.0.0.1"))
                try:
                    port = int(self.settings.get("web_port", 8765))
                except (TypeError, ValueError):
                    port = 8765
                try:
                    self.web = WebServer(self.core, host=host, port=port)
                except ValueError as exc:
                    self.ui.error(f"{exc}; using 127.0.0.1")
                    self.web = WebServer(self.core, host="127.0.0.1", port=port)
            if self.web.thread is None:
                self.web.start()
            self.ui.info(f"Browser interface: {self.web.url}")
            self.ui.info("Session token is embedded in the page; API calls require it.")
        elif operation == "stop":
            if self.web is not None and self.web.thread is not None:
                self.web.stop()
                self.ui.info("Browser interface stopped.")
            else:
                self.ui.info("Browser interface is not running.")
        else:
            if self.web is not None and self.web.thread is not None:
                self.ui.info(f"Browser interface: {self.web.url}")
            else:
                self.ui.info("Browser interface is not running. Use /web start.")

    # ---- menu items ------------------------------------------------------
    def _menu_item(self, number: str) -> None:
        name = MENU_NAMES[number]
        handlers = {
            "1": self._menu_chat,
            "2": self._menu_coding,
            "3": self._menu_projects,
            "4": self._menu_terminal,
            "5": self._security,
            "6": self._menu_research,
            "7": self._menu_automation,
            "8": self._history,
            "9": self._menu_monitor,
            "10": self._config,
        }
        self.ui.section(name.upper())
        handlers[number]()

    def _menu_chat(self) -> None:
        self.ui.info("Type a question at the raks > prompt to chat.")
        status = self.engine.status()
        self.ui.info(f"route={status['mode']} | local={status['local']} | online={status['online']}")

    def _menu_coding(self) -> None:
        self.ui.info("Languages: " + ", ".join(self.coding.languages()))
        self.ui.info("Use /code scaffold LANG DIR or /code validate PATH.")

    def _menu_projects(self) -> None:
        self._project("list")
        self._show_result(self.tools.execute("git_status"))

    def _menu_terminal(self) -> None:
        self.ui.info("Tools: " + ", ".join(self.core.tool_names()))
        self.ui.info("Arbitrary natural-language shell execution is disabled.")

    def _menu_research(self) -> None:
        self.ui.info(
            "Web research is available through the optional online AI provider only. "
            "No dedicated crawler is included in v1.0.1."
        )
        self.ui.info(f"online provider: {self.engine.status()['online']}")

    def _menu_automation(self) -> None:
        self.ui.info("Automations: " + ", ".join(self.automation.names()))
        self.ui.info("Use /automate NAME to run one. GitHub writes require explicit approval.")

    def _menu_monitor(self) -> None:
        self.ui.status_report(self.status)
        usage = system.process_usage()
        self.ui.info(f"process RSS: {system.format_bytes(usage['rss_kb'] * 1024)}")
        self.ui.info(f"memory stats: {self.memory.stats()}")


def main() -> int:
    RaksApp().run()
    return 0
