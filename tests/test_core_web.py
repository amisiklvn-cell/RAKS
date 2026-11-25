import json
import tempfile
import unittest

import raks
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from raks.config import load_settings, VERSION
from raks.core import RAKSCore
from raks.engine import EngineResponse
from raks.memory import MemoryStore
from raks.tools import ToolExecutor
from raks.web import JS, WebServer
from tests import AutoGate


class FakeEngine:
    def __init__(self):
        self.calls = []

    def status(self):
        return {"mode": "auto", "local": "fake", "online": "fake"}

    def respond(self, prompt, history=None):
        self.calls.append((prompt, history or []))
        return EngineResponse(True, "fake answer", "local", "fake", "fake-model", 3)


def make_core(tmp):
    engine = FakeEngine()
    memory = MemoryStore(str(Path(tmp) / "memory.db"))
    tools = ToolExecutor({"workspaces": [tmp]}, AutoGate())
    return RAKSCore(load_settings(), engine, memory, tools), engine


def request(
    base,
    path,
    method="GET",
    payload=None,
    token=None,
    cookie=True,
    origin=None,
    content_type="application/json",
    raw_body=None,
):
    headers = {}
    if token:
        headers["X-RAKS-Token"] = token
        if cookie:
            headers["Cookie"] = f"raks_session={token}"
    if origin:
        headers["Origin"] = origin
    body = raw_body
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = content_type
    elif raw_body is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        headers = dict(error.headers)
        error.close()
        return error.code, headers, body


class CoreTests(unittest.TestCase):
    def test_chat_persists_and_builds_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            core, engine = make_core(tmp)
            first = core.chat("first question")
            self.assertTrue(first["available"])
            self.assertEqual(first["text"], "fake answer")
            self.assertEqual(engine.calls[0][1], [])

            second = core.chat("second question")
            passed = engine.calls[1][1]
            self.assertEqual(len(passed), 2)
            self.assertEqual(passed[0], {"role": "user", "content": "first question"})
            self.assertEqual(passed[1], {"role": "assistant", "content": "fake answer"})

            history = core.history()
            self.assertEqual(len(history), 4)
            self.assertEqual(history[-2]["content"], "second question")
            self.assertEqual(history[-1]["content"], "fake answer")
            core.close()

    def test_empty_prompt_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            core, _ = make_core(tmp)
            self.assertIn("error", core.chat("   "))
            core.close()

    def test_status_contains_engine_memory_and_workspaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            core, _ = make_core(tmp)
            status = core.status()
            self.assertEqual(status["engine"]["mode"], "auto")
            self.assertEqual(status["memory"]["messages"], 0)
            self.assertIn(str(Path(tmp).resolve()), status["workspaces"])
            core.close()

    def test_run_tool_uses_shared_executor(self):
        with tempfile.TemporaryDirectory() as tmp:
            core, _ = make_core(tmp)
            result = core.run_tool("write_file", {"path": "note.txt", "content": "ok"})
            self.assertTrue(result.success)
            read = core.run_tool("read_file", {"path": "note.txt"})
            self.assertEqual(read.data["content"], "ok")
            core.close()

    def test_conversation_helpers_switch_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            core, _ = make_core(tmp)
            first = core.new_conversation("first")
            core.chat("first message")
            second = core.new_conversation("second")
            core.chat("second message")

            self.assertTrue(core.switch_conversation(first))
            self.assertIn("first message", [row["content"] for row in core.history(20)])
            self.assertNotIn("second message", [row["content"] for row in core.history(20)])

            self.assertTrue(core.switch_conversation(second))
            self.assertIn("second message", [row["content"] for row in core.history(20)])
            self.assertGreaterEqual(len(core.conversations()), 2)
            self.assertFalse(core.switch_conversation("0" * 32))
            core.close()


class MetadataTests(unittest.TestCase):
    def test_release_metadata_is_consistent(self):
        self.assertEqual(raks.__version__, VERSION)
        pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn(f'version = "{VERSION}"', pyproject)
        self.assertIn('requires-python = ">=3.12"', pyproject)


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core, self.engine = make_core(self.tmp.name)
        with patch("raks.web.logger.log"):
            self.server = WebServer(self.core, host="127.0.0.1", port=0)
            self.server.start()
        self.base = self.server.url
        self.token = self.server.session_token
        self.origin = f"http://127.0.0.1:{self.server.port}"

    def tearDown(self):
        self.server.stop()
        self.core.close()
        self.tmp.cleanup()

    def authorized(self, path, method="GET", payload=None, **kwargs):
        return request(
            self.base,
            path,
            method=method,
            payload=payload,
            token=self.token,
            origin=self.origin,
            **kwargs,
        )

    def test_index_contains_session_token_and_version(self):
        status, _, body = request(self.base, "/")
        self.assertEqual(status, 200)
        self.assertIn(self.token, body)
        self.assertIn(VERSION, body)
        self.assertIn('id="conversation-select"', body)

    def test_javascript_uses_history_messages_shape(self):
        self.assertIn("data.messages.forEach", JS)
        self.assertNotIn("history.forEach", JS)
        self.assertIn("X-RAKS-Token", JS)

    def test_api_requires_token_and_cookie(self):
        self.assertEqual(request(self.base, "/api/status")[0], 401)
        self.assertEqual(request(self.base, "/api/status", token=self.token, cookie=False)[0], 401)
        self.assertEqual(request(self.base, "/api/status", token="wrong")[0], 401)
        status, _, body = request(self.base, "/api/status", token=self.token)
        self.assertEqual(status, 200)
        self.assertIn("engine", json.loads(body))

    def test_unauthorized_post_does_not_reach_core(self):
        status, _, _ = request(
            self.base, "/api/chat", method="POST", payload={"prompt": "hello"}
        )
        self.assertEqual(status, 401)
        self.assertEqual(self.engine.calls, [])

    def test_cross_origin_post_is_rejected(self):
        status, _, body = request(
            self.base,
            "/api/chat",
            method="POST",
            payload={"prompt": "hello"},
            token=self.token,
            origin="https://evil.example",
        )
        self.assertEqual(status, 403)
        self.assertIn("forbidden", json.loads(body)["error"])
        self.assertEqual(self.engine.calls, [])

    def test_content_type_is_enforced(self):
        status, _, _ = request(
            self.base,
            "/api/chat",
            method="POST",
            token=self.token,
            origin=self.origin,
            raw_body=b'{"prompt":"hello"}',
            content_type="text/plain",
        )
        self.assertEqual(status, 415)
        self.assertEqual(self.engine.calls, [])

    def test_valid_chat_and_history_endpoints(self):
        status, _, body = self.authorized("/api/chat", method="POST", payload={"prompt": "browser hello"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["text"], "fake answer")
        status, _, body = self.authorized("/api/history?limit=5")
        self.assertEqual(status, 200)
        messages = json.loads(body)["messages"]
        self.assertTrue(any(item["content"] == "browser hello" for item in messages))

    def test_conversations_are_isolated_over_http(self):
        status, _, body = self.authorized("/api/conversations", method="POST", payload={"title": "work"})
        self.assertEqual(status, 201)
        work_id = json.loads(body)["id"]
        self.authorized("/api/chat", method="POST", payload={"prompt": "work secret"})

        status, _, body = self.authorized("/api/conversations", method="POST", payload={"title": "home"})
        self.assertEqual(status, 201)
        home_id = json.loads(body)["id"]
        self.authorized("/api/chat", method="POST", payload={"prompt": "home secret"})

        self.authorized("/api/conversations/switch", method="POST", payload={"id": work_id})
        _, _, body = self.authorized("/api/history")
        contents = [item["content"] for item in json.loads(body)["messages"]]
        self.assertIn("work secret", contents)
        self.assertNotIn("home secret", contents)

        self.authorized("/api/conversations/switch", method="POST", payload={"id": home_id})
        _, _, body = self.authorized("/api/history")
        contents = [item["content"] for item in json.loads(body)["messages"]]
        self.assertIn("home secret", contents)
        self.assertNotIn("work secret", contents)

    def test_no_tool_execution_endpoint(self):
        with patch.object(self.core, "run_tool") as spy:
            self.assertEqual(request(self.base, "/api/tools", token=self.token)[0], 200)
            self.assertEqual(
                request(self.base, "/api/tools", method="POST", payload={}, token=self.token)[0],
                404,
            )
            self.assertEqual(
                request(self.base, "/api/tools/run", method="POST", payload={}, token=self.token)[0],
                404,
            )
            spy.assert_not_called()

    def test_loopback_only_binding(self):
        for host in ("0.0.0.0", "192.168.1.2", "example.com"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                WebServer(self.core, host=host, port=0)

    def test_safe_error_responses(self):
        status, headers, body = self.authorized("/missing")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body), {"error": "not found"})
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("Content-Security-Policy", headers)
        self.assertNotIn("Traceback", body)
        self.assertNotIn("Secure", headers.get("Server", ""))

    def test_request_size_limit(self):
        huge = "x" * 120_000
        status, _, body = self.authorized(
            "/api/chat", method="POST", payload={"prompt": huge}
        )
        self.assertEqual(status, 400)
        self.assertIn("size", json.loads(body)["error"])
