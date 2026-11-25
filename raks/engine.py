"""AI engine boundary.

Stage 1 deliberately provides no responses. This makes it impossible for RAKS
to pretend to be intelligent before the real hybrid engine exists in Stage 2.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineResponse:
    implemented: bool
    text: str
    route: str = "none"


class AIEngine:
    name = "hybrid-router-placeholder"

    def route(self, prompt: str) -> str:
        return "none"

    def respond(self, prompt: str) -> EngineResponse:
        return EngineResponse(
            implemented=False,
            text=(
                "AI Conversation is not implemented yet in v0.1.0. "
                "Stage 2 will add local-first routing with optional online fallback."
            ),
            route="none",
        )
