"""Real AI provider adapters.

No model weights are downloaded. Local inference is used only when the user has
already installed a compatible llama.cpp CLI and configured a model path.
Online providers are optional and never required.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProviderUnavailable(RuntimeError):
    """Raised when a configured provider cannot produce a response."""


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    provider: str
    model: str
    latency_ms: int


def _messages_to_prompt(messages: List[Dict[str, str]]) -> str:
    """Flatten chat messages for local CLI models."""
    parts = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            parts.append(content)
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
        else:
            parts.append(f"User: {content}")
    return "\n\n".join(parts)


class LocalProvider:
    """Adapter for a locally installed llama.cpp `llama-cli` binary."""

    name = "local"

    def __init__(self, settings: Dict[str, Any]) -> None:
        self.settings = settings
        configured = str(settings.get("local_cli") or "").strip()
        self.cli = configured or shutil.which("llama-cli") or ""
        self.model = str(settings.get("local_model") or "").strip()
        self.max_tokens = int(settings.get("local_max_tokens") or 256)

    def available(self) -> bool:
        if not self.model or not Path(self.model).is_file():
            return False
        if not self.cli:
            return False
        if Path(self.cli).is_file():
            return os.access(self.cli, os.X_OK)
        return shutil.which(self.cli) is not None

    def status(self) -> str:
        if self.available():
            return f"ready ({Path(self.model).name})"
        return "not configured (no local model/cli)"

    def generate(
        self,
        messages: List[Dict[str, str]],
        timeout: Optional[float] = None,
    ) -> ProviderResponse:
        if not self.available():
            raise ProviderUnavailable(self.status())

        prompt = _messages_to_prompt(messages)
        command = [
            self.cli,
            "-m", self.model,
            "-p", prompt,
            "-n", str(self.max_tokens),
        ]
        limit = float(timeout or self.settings.get("request_timeout") or 120)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=limit,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ProviderUnavailable(f"local inference failed: {exc}") from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip().splitlines()[-1:] or ["unknown error"]
            raise ProviderUnavailable(f"local inference exited {completed.returncode}: {detail[0]}")
        output = completed.stdout.strip()
        if output.startswith(prompt):
            output = output[len(prompt):].strip()
        if not output:
            raise ProviderUnavailable("local inference returned empty output")
        return ProviderResponse(
            text=output,
            provider=self.name,
            model=Path(self.model).name,
            latency_ms=int((time.monotonic() - started) * 1000),
        )


class OnlineProvider:
    """Adapter for free no-key endpoints and optional keyed gateways."""

    ENDPOINTS = {
        "pollinations": "https://text.pollinations.ai/openai",
        "opencode": "https://opencode.ai/inference/openai/v1/chat/completions",
    }
    DEFAULT_MODELS = {
        "pollinations": "openai",
        "opencode": "deepseek-v4.1-flash-free",
    }

    def __init__(self, settings: Dict[str, Any]) -> None:
        self.settings = settings
        self.name = str(settings.get("online_provider") or "pollinations").lower()
        if self.name not in self.ENDPOINTS:
            self.name = "pollinations"
        self.model = str(settings.get("online_model") or self.DEFAULT_MODELS[self.name])
        key_env = str(settings.get("online_key_env") or "").strip()
        self.api_key = os.environ.get(key_env) if key_env else None
        if self.name == "opencode" and not self.api_key:
            self.api_key = "public"

    def available(self) -> bool:
        return True  # configured; actual reachability is checked during generate()

    def status(self) -> str:
        key_state = "key" if self.api_key and self.api_key != "public" else "no personal key"
        return f"configured ({self.name}, {key_state})"

    def _url_and_headers(self) -> tuple:
        url = self.ENDPOINTS[self.name]
        headers = {"Content-Type": "application/json", "User-Agent": "RAKS/1.0"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.name == "opencode":
            session = "ses_" + secrets.token_hex(12)
            headers.update(
                {
                    "Accept": "*/*",
                    "x-opencode-client": "cli",
                    "x-opencode-project": secrets.token_hex(20),
                    "x-opencode-session": session,
                    "x-opencode-session-id": session,
                    "x-session-affinity": session,
                    "X-Session-Id": session,
                }
            )
        if self.name == "pollinations" and self.api_key:
            url = "https://gen.pollinations.ai/v1/chat/completions"
        return url, headers

    def _payload(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "messages": messages,
        }
        if self.name == "opencode":
            payload["tools"] = [
                {"type": "function", "function": {"name": name}}
                for name in ("read", "write", "shell", "webfetch", "websearch")
            ]
            payload["tool_choice"] = "none"
        return payload

    def generate(
        self,
        messages: List[Dict[str, str]],
        timeout: Optional[float] = None,
    ) -> ProviderResponse:
        url, headers = self._url_and_headers()
        request = urllib.request.Request(
            url,
            data=json.dumps(self._payload(messages)).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        limit = float(timeout or self.settings.get("request_timeout") or 30)
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=limit) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise ProviderUnavailable(f"{self.name} returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderUnavailable(f"{self.name} unavailable: {exc}") from exc
        try:
            data = json.loads(body)
            choices = data.get("choices") or []
            text = choices[0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailable(f"{self.name} returned an unexpected response") from exc
        if not text:
            raise ProviderUnavailable(f"{self.name} returned empty output")
        return ProviderResponse(
            text=str(text),
            provider=self.name,
            model=self.model,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
