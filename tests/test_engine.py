import unittest

from raks.engine import HybridAIEngine
from raks.providers import ProviderResponse, ProviderUnavailable


class FakeProvider:
    def __init__(self, available, text=None, error=None, name="fake"):
        self._available = available
        self.text = text
        self.error = error
        self.name = name
        self.calls = []

    def available(self):
        return self._available

    def status(self):
        return "fake"

    def generate(self, messages, timeout=None):
        self.calls.append(messages)
        if self.error:
            raise ProviderUnavailable(self.error)
        return ProviderResponse(self.text, self.name, "fake-model", 1)


class HybridEngineTests(unittest.TestCase):
    def make_engine(self, mode, local, online):
        return HybridAIEngine({"route_mode": mode, "request_timeout": 1}, local, online)

    def test_auto_prefers_local(self):
        local = FakeProvider(True, "local answer", name="local")
        online = FakeProvider(True, "online answer", name="online")
        engine = self.make_engine("auto", local, online)
        response = engine.respond("hello")
        self.assertEqual(response.text, "local answer")
        self.assertEqual(response.route, "local")
        self.assertEqual(len(online.calls), 0)

    def test_auto_falls_back_to_online(self):
        local = FakeProvider(True, error="model missing")
        online = FakeProvider(True, "online answer", name="online")
        engine = self.make_engine("auto", local, online)
        response = engine.respond("hello")
        self.assertEqual(response.text, "online answer")
        self.assertEqual(response.route, "online")

    def test_online_mode_never_uses_local(self):
        local = FakeProvider(True, "local answer", name="local")
        online = FakeProvider(True, "online answer", name="online")
        engine = self.make_engine("online", local, online)
        response = engine.respond("hello")
        self.assertEqual(response.text, "online answer")
        self.assertEqual(len(local.calls), 0)

    def test_offline_mode_without_model_reports_honestly(self):
        engine = self.make_engine("offline", FakeProvider(False), FakeProvider(True, "x"))
        response = engine.respond("hello")
        self.assertFalse(response.available)
        self.assertIn("No AI provider", response.text)
        self.assertEqual(response.route, "unavailable")

    def test_history_is_passed_to_provider(self):
        local = FakeProvider(True, "ok", name="local")
        engine = self.make_engine("local", local, FakeProvider(False))
        engine.respond("next", [{"role": "assistant", "content": "previous"}])
        messages = local.calls[0]
        self.assertEqual(messages[-1], {"role": "user", "content": "next"})
        self.assertEqual(messages[0]["role"], "assistant")
