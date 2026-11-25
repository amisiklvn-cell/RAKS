"""Hybrid AI engine with honest offline handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .providers import LocalProvider, OnlineProvider, ProviderResponse, ProviderUnavailable

ROUTE_MODES = ("auto", "local", "online", "offline")


@dataclass(frozen=True)
class EngineResponse:
    implemented: bool
    text: str
    route: str = "none"
    provider: str = "none"
    model: str = "none"
    latency_ms: int = 0
    error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.error is None


class HybridAIEngine:
    def __init__(
        self,
        settings: Dict[str, Any],
        local: Optional[LocalProvider] = None,
        online: Optional[OnlineProvider] = None,
    ) -> None:
        self.settings = settings
        self.mode = str(settings.get("route_mode") or "auto").lower()
        if self.mode not in ROUTE_MODES:
            self.mode = "auto"
        self.local = local if local is not None else LocalProvider(settings)
        self.online = online if online is not None else OnlineProvider(settings)

    def status(self) -> Dict[str, str]:
        return {
            "mode": self.mode,
            "local": self.local.status(),
            "online": self.online.status(),
        }

    def route(self, prompt: str = "") -> str:
        """Choose a route without performing inference."""
        if self.mode == "offline":
            return "local" if self.local.available() else "unavailable"
        if self.mode == "local":
            return "local" if self.local.available() else "unavailable"
        if self.mode == "online":
            return "online" if self.online.available() else "unavailable"
        return "local" if self.local.available() else "online"

    @staticmethod
    def _build_messages(prompt: str, history: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
        messages = list(history or [])
        messages.append({"role": "user", "content": prompt})
        return messages

    def _unavailable(self, reason: str, route: str) -> EngineResponse:
        return EngineResponse(
            implemented=True,
            text=(
                "No AI provider is available right now. "
                f"Reason: {reason}. Configure a local model explicitly or use the free online provider."
            ),
            route=route,
            error=reason,
        )

    def respond(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> EngineResponse:
        route = self.route(prompt)
        if route == "unavailable":
            return self._unavailable(f"route mode '{self.mode}' has no usable provider", route)

        messages = self._build_messages(prompt, history)
        candidates = [route]
        if self.mode == "auto" and route == "local":
            candidates.append("online")

        errors: List[str] = []
        for candidate in candidates:
            provider = self.local if candidate == "local" else self.online
            try:
                result: ProviderResponse = provider.generate(messages)
            except ProviderUnavailable as exc:
                errors.append(f"{candidate}: {exc}")
                continue
            return EngineResponse(
                implemented=True,
                text=result.text,
                route=candidate,
                provider=result.provider,
                model=result.model,
                latency_ms=result.latency_ms,
            )
        return self._unavailable("; ".join(errors), route)
