"""Permission-controlled tool execution.

No natural-language input is ever passed to a shell. Tools are named operations
with structured arguments, workspace restrictions, approval gates, and backups
before risky changes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import logger
from .approval import ApprovalGate, ApprovalRequest, CLIApprovalGate, DenyGate
from .config import BACKUP_DIR, WORKSPACE_ROOT, load_settings, save_settings

APPROVAL_REQUIRED = frozenset(
    {
        "backup",
        "write_file",
        "create_dir",
        "move_file",
        "delete_file",
        "restore_backup",
        "install",
        "build",
        "build_apk",
        "run_tests",
        "compile_python",
        "git_commit",
        "git_push",
        "config_set",
        "execute_command",
    }
)

APPROVAL_REASONS = {
    "backup": "this creates an archive of workspace files",
    "write_file": "this modifies a file in the approved workspace",
    "create_dir": "this creates a directory",
    "move_file": "this moves a file",
    "delete_file": "this deletes a file after making a backup",
    "restore_backup": "this restores files from a backup",
    "build": "this starts a build",
    "build_apk": "this builds an Android APK",
    "run_tests": "this executes the project test suite",
    "compile_python": "this compiles Python sources",
    "git_commit": "this creates a Git commit",
    "git_push": "this publishes commits to GitHub",
    "config_set": "this changes RAKS configuration",
    "execute_command": "this executes a command",
}

TOOLS = (
    "status", "list_dir", "read_file", "write_file", "create_dir", "move_file",
    "delete_file", "backup", "restore_backup", "compile_python", "run_tests",
    "build_apk", "git_status", "git_log", "git_diff", "git_commit", "git_push",
    "config_get", "config_set", "security_scan", "execute_command",
)


class ToolResult:
    def __init__(
        self,
        implemented: bool,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.implemented = implemented
        self.success = success
        self.message = message
        self.data = data or {}

    def __repr__(self) -> str:
        return f"ToolResult(success={self.success}, message={self.message!r})"


def _ok(message: str, **data: Any) -> ToolResult:
    return ToolResult(True, True, message, data)


def _fail(message: str) -> ToolResult:
    return ToolResult(True, False, message)


class ToolExecutor:
    def __init__(
        self,
        settings: Optional[Dict[str, Any]] = None,
        gate: Optional[ApprovalGate] = None,
    ) -> None:
        self.settings = settings or load_settings()
        configured = self.settings.get("workspaces") or [str(WORKSPACE_ROOT)]
        self.workspaces = [Path(item).expanduser().resolve() for item in configured]
        if not any(str(path) == str(WORKSPACE_ROOT.resolve()) for path in self.workspaces):
            self.workspaces.append(WORKSPACE_ROOT.resolve())
        self.gate = gate if gate is not None else CLIApprovalGate()

    def requires_approval(self, tool_name: str) -> bool:
        return tool_name in APPROVAL_REQUIRED

    def _workspace_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self._default_workspace() / path
        resolved = path.resolve()
        if not any(resolved.is_relative_to(root) for root in self.workspaces):
            raise ValueError(f"path outside approved workspace: {resolved}")
        return resolved

    def _default_workspace(self) -> Path:
        return self.workspaces[0]

    def resolve_path(self, value: str) -> Path:
        """Public workspace-checked resolver for companion modules."""
        return self._workspace_path(value)

    def _backup_file(self, path: Path) -> Optional[str]:
        if not path.is_file():
            return None
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        destination = BACKUP_DIR / f"{path.name}.{stamp}.bak"
        shutil.copy2(path, destination)
        return str(destination)

    def _run(self, command: List[str], cwd: Path, timeout: int = 300) -> ToolResult:
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return _fail(f"command failed to start: {exc}")
        output = completed.stdout.strip()[-4000:]
        if completed.returncode != 0:
            return _fail(f"exit {completed.returncode}: {output}")
        return _ok("command completed", output=output)

    def execute(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        name = (tool_name or "").strip().lower()
        args = arguments or {}
        if name not in TOOLS:
            return ToolResult(False, False, f"Tool '{name}' is not implemented.")
        if name == "execute_command":
            return _fail("Arbitrary command execution is disabled by design.")

        if self.requires_approval(name):
            target = str(
                args.get("path") or args.get("src") or args.get("cwd") or self._default_workspace()
            )
            request = ApprovalRequest(
                operation=name,
                reason=APPROVAL_REASONS.get(name, "sensitive operation"),
                target=target,
                detail=str(args.get("message") or args.get("command") or "")[:300],
            )
            if not self.gate.approve(request):
                logger.log("tool_denied", tool=name)
                return _fail(f"approval denied for {name}")

        logger.log("tool_executed", tool=name)
        handler = getattr(self, f"_tool_{name}")
        try:
            return handler(args)
        except Exception as exc:
            return _fail(f"{type(exc).__name__}: {exc}")

    # ---- read-only tools -------------------------------------------------
    def _tool_status(self, args: Dict[str, Any]) -> ToolResult:
        return _ok(
            "tool executor ready",
            workspaces=[str(path) for path in self.workspaces],
            approval_required=sorted(APPROVAL_REQUIRED),
        )

    def _tool_list_dir(self, args: Dict[str, Any]) -> ToolResult:
        path = self._workspace_path(str(args.get("path") or self._default_workspace()))
        if not path.is_dir():
            return _fail("not a directory")
        entries = []
        for child in sorted(path.iterdir(), key=lambda item: item.name.lower()):
            entries.append({"name": child.name, "type": "dir" if child.is_dir() else "file"})
        return _ok(f"{len(entries)} entries", entries=entries)

    def _tool_read_file(self, args: Dict[str, Any]) -> ToolResult:
        if not args.get("path"):
            return _fail("path is required")
        path = self._workspace_path(str(args["path"]))
        if not path.is_file():
            return _fail("file not found")
        content = path.read_text(encoding="utf-8", errors="replace")[:200000]
        return _ok(f"read {path.name}", content=content)

    def _tool_config_get(self, args: Dict[str, Any]) -> ToolResult:
        settings = load_settings()
        key = args.get("key")
        value = settings.get(str(key)) if key else settings
        return _ok("configuration read", value=value)

    def _tool_git_status(self, args: Dict[str, Any]) -> ToolResult:
        return self._run(["git", "status", "--short", "--branch"], self._default_workspace())

    def _tool_git_log(self, args: Dict[str, Any]) -> ToolResult:
        limit = str(args.get("limit") or 5)
        return self._run(["git", "log", f"-{limit}", "--oneline"], self._default_workspace())

    def _tool_git_diff(self, args: Dict[str, Any]) -> ToolResult:
        return self._run(["git", "diff", "--stat", "HEAD"], self._default_workspace())

    # ---- mutating tools --------------------------------------------------
    def _tool_write_file(self, args: Dict[str, Any]) -> ToolResult:
        if not args.get("path") or "content" not in args:
            return _fail("path and content are required")
        path = self._workspace_path(str(args["path"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        backup = self._backup_file(path)
        path.write_text(str(args["content"]), encoding="utf-8")
        return _ok(f"wrote {path.name}", backup=backup)

    def _tool_create_dir(self, args: Dict[str, Any]) -> ToolResult:
        if not args.get("path"):
            return _fail("path is required")
        path = self._workspace_path(str(args["path"]))
        path.mkdir(parents=True, exist_ok=True)
        return _ok(f"created {path.name}")

    def _tool_move_file(self, args: Dict[str, Any]) -> ToolResult:
        if not args.get("src") or not args.get("dst"):
            return _fail("src and dst are required")
        source = self._workspace_path(str(args["src"]))
        destination = self._workspace_path(str(args["dst"]))
        if not source.is_file():
            return _fail("source file not found")
        destination.parent.mkdir(parents=True, exist_ok=True)
        backup = self._backup_file(source)
        shutil.move(str(source), str(destination))
        return _ok(f"moved to {destination.name}", backup=backup)

    def _tool_delete_file(self, args: Dict[str, Any]) -> ToolResult:
        if not args.get("path"):
            return _fail("path is required")
        path = self._workspace_path(str(args["path"]))
        if not path.is_file():
            return _fail("only single files can be deleted")
        backup = self._backup_file(path)
        path.unlink()
        return _ok(f"deleted {path.name}", backup=backup)

    def _tool_backup(self, args: Dict[str, Any]) -> ToolResult:
        paths = args.get("paths") or [str(self._default_workspace())]
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        archive = BACKUP_DIR / f"raks-backup-{stamp}.tar.gz"
        roots = [self._workspace_path(str(item)) for item in paths]
        with tarfile.open(archive, "w:gz") as tar:
            for root in roots:
                if root.is_file():
                    tar.add(root, arcname=root.name)
                elif root.is_dir():
                    tar.add(root, arcname=root.name)
        return _ok(f"backup created: {archive.name}", archive=str(archive))

    def _tool_restore_backup(self, args: Dict[str, Any]) -> ToolResult:
        if not args.get("archive"):
            return _fail("archive is required")
        archive = Path(str(args["archive"])).expanduser().resolve()
        if not archive.is_relative_to(BACKUP_DIR.resolve()):
            raise ValueError("archive must be inside the RAKS backup directory")
        target = self._workspace_path(str(args.get("target") or self._default_workspace()))
        restored = 0
        skipped = 0
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if Path(member.name).is_absolute() or ".." in parts:
                    skipped += 1
                    continue
                destination = (target / member.name).resolve()
                if not destination.is_relative_to(target):
                    skipped += 1
                    continue
                # Explicit data filter keeps traversal/symlink/lib extraction
                # protections independent of the interpreter's default policy.
                tar.extract(member, path=str(target), filter="data")
                restored += 1
        return _ok(
            f"restored {restored} entries, skipped {skipped} unsafe entries",
            restored=restored,
            skipped=skipped,
        )

    def _tool_config_set(self, args: Dict[str, Any]) -> ToolResult:
        key, value = args.get("key"), args.get("value")
        if not key:
            return _fail("key is required")
        settings = load_settings()
        settings[str(key)] = value
        path = save_settings(settings)
        return _ok(f"updated {key}", path=str(path))

    # ---- development tools ----------------------------------------------
    def _tool_compile_python(self, args: Dict[str, Any]) -> ToolResult:
        workspace = self._workspace_path(str(args.get("cwd") or self._default_workspace()))
        return self._run([sys.executable, "-m", "compileall", "-q", "raks", "tests"], workspace)

    def _tool_run_tests(self, args: Dict[str, Any]) -> ToolResult:
        workspace = self._workspace_path(str(args.get("cwd") or self._default_workspace()))
        return self._run([sys.executable, "-m", "unittest", "discover", "-v"], workspace)

    def _tool_build_apk(self, args: Dict[str, Any]) -> ToolResult:
        workspace = self._workspace_path(str(args.get("cwd") or self._default_workspace()))
        wrapper = workspace / "gradlew"
        if wrapper.is_file() and os.access(wrapper, os.X_OK):
            command = [str(wrapper), "assembleDebug", "--no-daemon"]
        elif shutil.which("gradle"):
            command = ["gradle", "assembleDebug", "--no-daemon"]
        else:
            return _fail("no Gradle wrapper or Gradle executable found")
        return self._run(command, workspace, timeout=1800)

    def _tool_git_commit(self, args: Dict[str, Any]) -> ToolResult:
        message = str(args.get("message") or "").strip()
        if not message:
            return _fail("commit message is required")
        paths = args.get("paths") or []
        if not isinstance(paths, list) or not paths:
            return _fail("explicit file paths are required; git add -A is disabled")
        workspace = self._default_workspace()
        relative = []
        for item in paths:
            resolved = self._workspace_path(str(item))
            relative.append(str(resolved.relative_to(workspace)))
        staged = self._run(["git", "add", "--", *relative], workspace)
        if not staged.success:
            return staged
        return self._run(["git", "commit", "-m", message], workspace)

    def _tool_git_push(self, args: Dict[str, Any]) -> ToolResult:
        remote = str(args.get("remote") or "origin")
        branch = str(args.get("branch") or "main")
        return self._run(["git", "push", remote, branch], self._default_workspace())

    def _tool_security_scan(self, args: Dict[str, Any]) -> ToolResult:
        from .security import scan_workspace

        workspace = self._workspace_path(str(args.get("path") or self._default_workspace()))
        report = scan_workspace(workspace)
        return _ok(report.summary, report=report.text)
