import json
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from raks.config import load_settings
from raks.core import RAKSCore
from raks.engine import EngineResponse, HybridAIEngine
from raks.memory import MemoryStore
from raks.tools import ToolExecutor
from raks.web import WebServer


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
    core = RAKSCore(load_settings(), engine, memory, tools)
    return core, engine


class AutoGate:
    def approve(self, request):
        return True


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


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core, self.engine = make_core(self.tmp.name)
        with patch("raks.web.logger.log"):
            self.server = WebServer(self.core, host="127.0.0.1", port=0)
            self.server.start()
        self.base = self.server.url

    def tearDown(self):
        self.server.stop()
        self.core.close()
        self.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            return response.status, response.read().decode("utf-8")

    def post(self, path, payload):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_index_page_loads(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("RAKS AI", body)
        self.assertIn("id=\"prompt\"", body)

    def test_status_and_history_endpoints(self):
        status, body = self.get("/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["engine"]["mode"], "auto")
        status, body = self.get("/api/history?limit=5")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["messages"], [])

    def test_chat_endpoint_uses_shared_core(self):
        status, body = self.post("/api/chat", {"prompt": "browser hello"})
        self.assertEqual(status, 200)
        self.assertEqual(body["text"], "fake answer")
        self.assertEqual(len(self.engine.calls), 1)
        _, history = self.get("/api/history")
        messages = json.loads(history)["messages"]
        self.assertTrue(any(item["content"] == "browser hello" for item in messages))

    def test_unknown_route_returns_404(self):
        with self.assertRaises(Exception):
            self.get("/missing")
