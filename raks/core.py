"""Shared RAKS application core used by terminal and browser interfaces."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import logger, system
from .config import load_settings
from .engine import EngineResponse, HybridAIEngine
from .memory import MemoryStore
from .tools import ToolExecutor, ToolResult


class RAKSCore:
    def __init__(
        self,
        settings: Optional[Dict[str, Any]] = None,
        engine: Optional[HybridAIEngine] = None,
        memory: Optional[MemoryStore] = None,
        tools: Optional[ToolExecutor] = None,
    ) -> None:
        self.settings = settings if settings is not None else load_settings()
        self.engine = engine if engine is not None else HybridAIEngine(self.settings)
        self.memory = memory if memory is not None else MemoryStore(
            enabled=bool(self.settings.get("memory_enabled", True))
        )
        self.tools = tools if tools is not None else ToolExecutor(self.settings)

    def chat(self, prompt: str) -> Dict[str, Any]:
        """Send one message through the shared engine and persist it."""
        prompt = (prompt or "").strip()
        if not prompt:
            return {"error": "empty prompt"}
        history = [
            {"role": item["role"], "content": item["content"]}
            for item in self.memory.recent(20)
        ]
        history.reverse()
        self.memory.remember("user", prompt)
        response: EngineResponse = self.engine.respond(prompt, history)
        if response.available:
            self.memory.remember("assistant", response.text)
        logger.log("chat", route=response.route)
        return {
            "text": response.text,
            "route": response.route,
            "provider": response.provider,
            "model": response.model,
            "latency_ms": response.latency_ms,
            "available": response.available,
            "error": response.error,
        }

    def history(
        self,
        limit: int = 20,
        conversation_id: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        rows = self.memory.recent(limit, conversation_id=conversation_id)
        rows.reverse()
        return rows

    def conversations(self) -> List[Dict[str, Any]]:
        return self.memory.conversations()

    def new_conversation(self, title: str = "default") -> str:
        return self.memory.start_conversation(title)

    def switch_conversation(self, conversation_id: str) -> bool:
        return self.memory.switch_conversation(conversation_id)

    def status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = system.collect_system_status()
        status["engine"] = self.engine.status()
        status["memory"] = self.memory.stats()
        status["workspaces"] = [str(path) for path in self.tools.workspaces]
        return status

    def run_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> ToolResult:
        return self.tools.execute(name, arguments or {})

    def tool_names(self) -> List[str]:
        from .tools import TOOLS

        return list(TOOLS)

    def close(self) -> None:
        self.memory.close()
