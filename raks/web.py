"""Local browser chat interface backed by the shared RAKS core.

The server binds to 127.0.0.1 by default and uses only the standard library.
Browser requests use the same RAKSCore as the terminal.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlsplit

from . import logger
from .core import RAKSCore

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RAKS AI</title>
<link rel="stylesheet" href="/style.css">
</head>
<body>
<main>
<header>
<h1>RAKS AI</h1>
<p>Version 1.0.0 &middot; local browser interface</p>
</header>
<section id="status">Loading status...</section>
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
#status { border:1px solid #ff3b4e; padding:10px; margin:16px 0; color:#00e5ff; font-size:12px; }
#messages { min-height:320px; max-height:60vh; overflow:auto; border:1px solid #00e5ff; padding:12px; }
.msg { margin:8px 0; white-space:pre-wrap; }
.msg.user { color:#ff6b78; }
.msg.assistant { color:#7ffcff; }
form { display:flex; gap:8px; margin-top:12px; }
input { flex:1; background:#000; color:#00e5ff; border:1px solid #00e5ff; padding:10px; font-family:monospace; }
button { background:#ff3b4e; color:#000; border:0; padding:10px 18px; font-weight:bold; cursor:pointer; }
.error { color:#ff3b4e; min-height:18px; }
"""

JS = """
const messages = document.getElementById('messages');
const errorBox = document.getElementById('error');
function addMessage(role, text) {
  const line = document.createElement('div');
  line.className = 'msg ' + role;
  line.textContent = role + '> ' + text;
  messages.appendChild(line);
  messages.scrollTop = messages.scrollHeight;
}
async function load() {
  const status = await fetch('/api/status').then(r => r.json());
  document.getElementById('status').textContent =
    'Route: ' + status.engine.mode + ' | Local: ' + status.engine.local +
    ' | Online: ' + status.engine.online + ' | Memory: ' + status.memory.messages;
  const history = await fetch('/api/history?limit=20').then(r => r.json());
  history.forEach(item => addMessage(item.role, item.content));
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
    const response = await fetch('/api/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({prompt})
    }).then(r => r.json());
    if (response.error) errorBox.textContent = response.error;
    addMessage('assistant', response.text || 'No response.');
  } catch (error) {
    errorBox.textContent = String(error);
  }
});
load();
"""


def make_handler(core: RAKSCore):
    class RAKSHandler(BaseHTTPRequestHandler):
        server_version = "RAKS/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            logger.log("web_request", method=getattr(self, "command", "?"), path=self.path[:120])

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: Dict[str, Any]) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            path = parsed.path
            if path in ("/", "/index.html"):
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/style.css":
                self._send(200, CSS.encode("utf-8"), "text/css; charset=utf-8")
            elif path == "/app.js":
                self._send(200, JS.encode("utf-8"), "application/javascript; charset=utf-8")
            elif path == "/api/status":
                self._json(200, core.status())
            elif path == "/api/history":
                query = parse_qs(parsed.query)
                try:
                    limit = int(query.get("limit", ["20"])[0])
                except ValueError:
                    limit = 20
                self._json(200, {"messages": core.history(limit)})
            elif path == "/api/tools":
                self._json(200, {"tools": core.tool_names()})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path != "/api/chat":
                self._json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 100000:
                self._json(400, {"error": "invalid request size"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                prompt = str(payload.get("prompt") or "")
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                self._json(400, {"error": "invalid JSON"})
                return
            self._json(200, core.chat(prompt))

    return RAKSHandler


class WebServer:
    def __init__(self, core: RAKSCore, host: str = "127.0.0.1", port: int = 0) -> None:
        self.core = core
        handler = make_handler(core)
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.host, self.port = self.httpd.server_address[:2]
        self.thread: Optional[threading.Thread] = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

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
