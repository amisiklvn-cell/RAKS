"""Hardened local browser interface backed by the shared RAKS core.

The server is loopback-only, issues a random per-session token, requires that
token plus a matching SameSite cookie for every API request, and validates the
Origin on state-changing requests. Only fixed in-memory assets are served; no
filesystem path is ever derived from a request.
"""

from __future__ import annotations

import ipaddress
import json
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlsplit

from . import logger
from .core import RAKSCore
from .config import VERSION

MAX_BODY_BYTES = 100_000
MAX_PROMPT_CHARS = 8_000
CONVERSATION_ID = re.compile(r"^[0-9a-f]{32}$")

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="raks-token" content="__RAKS_TOKEN__">
<title>RAKS AI</title>
<link rel="stylesheet" href="/style.css">
</head>
<body>
<main>
<header>
<h1>RAKS AI</h1>
<p>Version __RAKS_VERSION__ &middot; local browser interface</p>
</header>
<section id="status">Loading status...</section>
<section id="conversation">
<label for="conversation-select">Conversation</label>
<select id="conversation-select"></select>
<button id="new-conversation" type="button">New</button>
</section>
<section id="messages" aria-live="polite"></section>
<form id="composer">
<input id="prompt" autocomplete="off" placeholder="Ask RAKS something...">
<button type="submit">Send</button>
</form>
<p id="error" class="error"></p>
</main>
<script src="/app.js"></script>
</body>
</html>
"""

CSS = """
* { box-sizing: border-box; }
body { margin:0; background:#000; color:#d8faff; font-family:monospace; }
main { max-width:860px; margin:0 auto; padding:24px; }
h1 { color:#ff3b4e; letter-spacing:6px; margin:0; }
header p { color:#00e5ff; font-size:13px; }
#status, #conversation { border:1px solid #ff3b4e; padding:10px; margin:16px 0; color:#00e5ff; font-size:12px; }
#messages { min-height:320px; max-height:60vh; overflow:auto; border:1px solid #00e5ff; padding:12px; }
.msg { margin:8px 0; white-space:pre-wrap; }
.msg.user { color:#ff6b78; }
.msg.assistant { color:#7ffcff; }
form { display:flex; gap:8px; margin-top:12px; }
input, select { background:#000; color:#00e5ff; border:1px solid #00e5ff; padding:10px; font-family:monospace; }
button { background:#ff3b4e; color:#000; border:0; padding:10px 18px; font-weight:bold; cursor:pointer; }
.error { color:#ff3b4e; min-height:18px; }
"""

JS = """
const tokenMeta = document.querySelector('meta[name="raks-token"]');
const sessionToken = tokenMeta ? tokenMeta.content : '';
const messages = document.getElementById('messages');
const errorBox = document.getElementById('error');
const conversationSelect = document.getElementById('conversation-select');

function addMessage(role, text) {
  const line = document.createElement('div');
  line.className = 'msg ' + role;
  line.textContent = role + '> ' + text;
  messages.appendChild(line);
  messages.scrollTop = messages.scrollHeight;
}

async function api(path, options) {
  const request = Object.assign({}, options || {});
  request.headers = Object.assign({'X-RAKS-Token': sessionToken}, request.headers || {});
  const response = await fetch(path, request);
  if (response.status === 401 || response.status === 403) {
    throw new Error('Session rejected. Reload this page to get a new token.');
  }
  return response;
}

async function loadConversations() {
  const response = await api('/api/conversations');
  const data = await response.json();
  conversationSelect.replaceChildren();
  for (const item of data.conversations) {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.title + ' (' + item.messages + ')';
    option.selected = Boolean(item.active);
    conversationSelect.appendChild(option);
  }
}

async function loadHistory() {
  const response = await api('/api/history?limit=20');
  const data = await response.json();
  messages.replaceChildren();
  data.messages.forEach(item => addMessage(item.role, item.content));
}

async function load() {
  try {
    const status = await api('/api/status').then(r => r.json());
    document.getElementById('status').textContent =
      'Route: ' + status.engine.mode + ' | Local: ' + status.engine.local +
      ' | Online: ' + status.engine.online + ' | Memory: ' + status.memory.messages;
    await loadConversations();
    await loadHistory();
  } catch (error) {
    errorBox.textContent = String(error);
  }
}

document.getElementById('composer').addEventListener('submit', async (event) => {
  event.preventDefault();
  const input = document.getElementById('prompt');
  const prompt = input.value.trim();
  if (!prompt) return;
  input.value = '';
  addMessage('user', prompt);
  errorBox.textContent = '';
  try {
    const response = await api('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt})
    }).then(r => r.json());
    if (response.error) errorBox.textContent = response.error;
    addMessage('assistant', response.text || 'No response.');
  } catch (error) {
    errorBox.textContent = String(error);
  }
});

conversationSelect.addEventListener('change', async (event) => {
  try {
    await api('/api/conversations/switch', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id: event.target.value})
    });
    await loadHistory();
  } catch (error) {
    errorBox.textContent = String(error);
  }
});

document.getElementById('new-conversation').addEventListener('click', async () => {
  const title = window.prompt('Conversation title', 'New conversation');
  if (!title) return;
  try {
    await api('/api/conversations', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({title})
    });
    await loadConversations();
    await loadHistory();
  } catch (error) {
    errorBox.textContent = String(error);
  }
});

load();
"""

ENDPOINTS = {
    "/": "page",
    "/index.html": "page",
    "/style.css": "asset_css",
    "/app.js": "asset_js",
    "/api/status": "status",
    "/api/history": "history",
    "/api/tools": "tools",
    "/api/conversations": "conversations",
    "/api/conversations/switch": "conversation_switch",
    "/api/chat": "chat",
}


def _normalise_loopback(host: str) -> str:
    value = str(host or "127.0.0.1").strip().lower()
    if value in ("localhost", "127.0.0.1"):
        return "127.0.0.1"
    if value in ("::1", "[::1]"):
        return "::1"
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("web_host must be a loopback address") from exc
    if not address.is_loopback:
        raise ValueError("web_host must be a loopback address")
    return str(address)


class _RAKSServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(core: RAKSCore):
    class RAKSHandler(BaseHTTPRequestHandler):
        server_version = "RAKS"
        sys_version = ""
        protocol_version = "HTTP/1.1"
        timeout = 15

        def log_message(self, fmt: str, *args: Any) -> None:
            logger.log(
                "web_request",
                method=getattr(self, "command", "?"),
                endpoint=ENDPOINTS.get(urlsplit(self.path).path, "unknown"),
            )

        def _send(
            self,
            status: int,
            body: bytes,
            content_type: str,
            extra_headers: Optional[Dict[str, str]] = None,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'none'; base-uri 'none'; form-action 'self'",
            )
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _json(
            self,
            status: int,
            payload: Dict[str, Any],
            extra_headers: Optional[Dict[str, str]] = None,
        ) -> None:
            self._send(
                status,
                json.dumps(payload).encode("utf-8"),
                "application/json",
                extra_headers,
            )

        def send_error(self, code: int, message: Optional[str] = None, explain: Optional[str] = None) -> None:
            self._json(code, {"error": "request failed", "code": code})

        def _cookie_value(self, name: str) -> str:
            for part in self.headers.get("Cookie", "").split(";"):
                key, _, value = part.strip().partition("=")
                if key == name:
                    return value
            return ""

        def _authorized(self) -> bool:
            expected = getattr(self.server, "session_token", "")
            supplied = self.headers.get("X-RAKS-Token", "")
            cookie = self._cookie_value("raks_session")
            return (
                bool(expected)
                and secrets.compare_digest(supplied, expected)
                and secrets.compare_digest(cookie, expected)
            )

        def _require_auth(self) -> bool:
            if self._authorized():
                return True
            self.close_connection = True
            self._json(
                401,
                {"error": "unauthorized"},
                {"WWW-Authenticate": 'Bearer realm="RAKS"'},
            )
            return False

        def _origin_valid(self) -> bool:
            origin = self.headers.get("Origin")
            if origin is not None and origin not in getattr(self.server, "allowed_origins", set()):
                return False
            if self.headers.get("Sec-Fetch-Site", "") == "cross-site":
                return False
            return True

        def _post_common(self) -> Optional[int]:
            """Return validated body length, or None after sending an error."""
            if not self._require_auth():
                return None
            if not self._origin_valid():
                self.close_connection = True
                self._json(403, {"error": "forbidden origin"})
                return None
            if self.headers.get("Transfer-Encoding"):
                self.close_connection = True
                self._json(400, {"error": "unsupported transfer encoding"})
                return None
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self.close_connection = True
                self._json(415, {"error": "application/json required"})
                return None
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY_BYTES:
                self.close_connection = True
                self._json(400, {"error": "invalid request size"})
                return None
            return length

        def _read_json(self, length: int) -> Optional[Dict[str, Any]]:
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
            return payload if isinstance(payload, dict) else None

        def _page(self) -> bytes:
            return (
                PAGE.replace("__RAKS_TOKEN__", self.server.session_token)
                .replace("__RAKS_VERSION__", VERSION)
                .encode("utf-8")
            )

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            path = parsed.path
            if path in ("/", "/index.html"):
                cookie = f"raks_session={self.server.session_token}; HttpOnly; SameSite=Strict; Path=/"
                self._send(200, self._page(), "text/html; charset=utf-8", {"Set-Cookie": cookie})
                return
            if path == "/style.css":
                self._send(200, CSS.encode("utf-8"), "text/css; charset=utf-8")
                return
            if path == "/app.js":
                self._send(200, JS.encode("utf-8"), "application/javascript; charset=utf-8")
                return
            if not self._require_auth():
                return
            if path == "/api/status":
                self._json(200, core.status())
                return
            if path == "/api/history":
                query = parse_qs(parsed.query)
                try:
                    limit = int(query.get("limit", ["20"])[0])
                except ValueError:
                    limit = 20
                conversation_id = query.get("conversation_id", [None])[0]
                if conversation_id is not None and not CONVERSATION_ID.fullmatch(conversation_id):
                    self._json(400, {"error": "invalid conversation id"})
                    return
                self._json(200, {"messages": core.history(limit, conversation_id)})
                return
            if path == "/api/conversations":
                self._json(200, {"conversations": core.conversations()})
                return
            if path == "/api/tools":
                self._json(200, {"tools": core.tool_names()})
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if path not in ("/api/chat", "/api/conversations", "/api/conversations/switch"):
                self._json(404, {"error": "not found"})
                return
            length = self._post_common()
            if length is None:
                return
            payload = self._read_json(length)
            if payload is None:
                self._json(400, {"error": "invalid JSON"})
                return

            if path == "/api/chat":
                prompt = payload.get("prompt")
                if not isinstance(prompt, str) or not prompt.strip():
                    self._json(400, {"error": "prompt is required"})
                    return
                if len(prompt) > MAX_PROMPT_CHARS:
                    self._json(400, {"error": "prompt is too long"})
                    return
                self._json(200, core.chat(prompt))
                return

            if path == "/api/conversations":
                title = payload.get("title")
                if not isinstance(title, str) or not title.strip() or len(title) > 120:
                    self._json(400, {"error": "invalid conversation title"})
                    return
                conversation_id = core.new_conversation(title.strip())
                self._json(201, {"id": conversation_id, "conversations": core.conversations()})
                return

            conversation_id = payload.get("id")
            if not isinstance(conversation_id, str) or not CONVERSATION_ID.fullmatch(conversation_id):
                self._json(400, {"error": "invalid conversation id"})
                return
            if not core.switch_conversation(conversation_id):
                self._json(404, {"error": "conversation not found"})
                return
            self._json(200, {"ok": True, "conversations": core.conversations()})

    return RAKSHandler


class WebServer:
    def __init__(self, core: RAKSCore, host: str = "127.0.0.1", port: int = 0) -> None:
        self.core = core
        self.host = _normalise_loopback(host)
        handler = make_handler(core)
        self.httpd = _RAKSServer((self.host, port), handler)
        self.host, self.port = self.httpd.server_address[:2]
        self.session_token = secrets.token_urlsafe(32)
        self.httpd.session_token = self.session_token
        display_host = f"[{self.host}]" if ":" in self.host else self.host
        self.httpd.allowed_origins = {
            f"http://{display_host}:{self.port}",
            "http://localhost:{0}".format(self.port),
        }
        self.thread: Optional[threading.Thread] = None

    @property
    def url(self) -> str:
        display_host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{display_host}:{self.port}"

    def start(self) -> None:
        if self.thread is None:
            self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        if self.thread is not None:
            self.thread.join(timeout=5)
            self.thread = None
