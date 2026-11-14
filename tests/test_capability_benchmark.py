import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from brain.model_types import ModelResponse, ToolCall
from core.application import SeedApplication
from memory import store
from runtime import workspace_guard


class BenchmarkGateway:
    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, request, provider_name=None):
        return self.responses.pop(0)


class CapabilityBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "benchmark.sqlite"
        self.workspace = Path(self.tmp.name) / "workspace"
        self.workspace.mkdir()
        (self.workspace / "benchmark.txt").write_text("benchmark", encoding="utf-8")
        self.db_patch = patch.object(store, "DB_PATH", self.db)
        self.workspace_patch = patch.object(workspace_guard, "WORKSPACE", self.workspace)
        self.db_patch.start()
        self.workspace_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.workspace_patch.stop)

    def test_system_tool_selection_and_persistence(self):
        gateway = BenchmarkGateway([
            ModelResponse("", "benchmark", "fake", (
                ToolCall("1", "system.health", {}),
            )),
            ModelResponse("BENCHMARK_HEALTH_OK", "benchmark", "fake"),
        ])
        app = SeedApplication(gateway=gateway)
        started = time.perf_counter()
        result = app.seed_request("Check runtime health and report the result.")
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.response, "BENCHMARK_HEALTH_OK")
        self.assertEqual(result.tool_results[0]["status"], "success")
        events = [row["event_type"] for row in store.get_task_events(result.task_id)]
        self.assertIn("permission_decision", events)
        self.assertIn("tool_completed", events)
        self.assertIn("response_completed", events)
        self.assertGreater(elapsed_ms, 0)

    def test_unknown_tool_is_denied_without_execution(self):
        gateway = BenchmarkGateway([
            ModelResponse("", "benchmark", "fake", (
                ToolCall("1", "system.unknown", {}),
            )),
            ModelResponse("BENCHMARK_DENIED_OK", "benchmark", "fake"),
        ])
        app = SeedApplication(gateway=gateway)
        result = app.seed_request("Use only the requested tool.")

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.tool_results[0]["status"], "denied")
        self.assertIn("not registered", result.tool_results[0]["reason"])
        events = [row["event_type"] for row in store.get_task_events(result.task_id)]
        self.assertIn("tool_denied", events)

    def test_arabic_request_preserves_user_input_in_session(self):
        gateway = BenchmarkGateway([
            ModelResponse("اختبار عربي ناجح", "benchmark", "fake"),
        ])
        app = SeedApplication(gateway=gateway)
        result = app.seed_request("تحقق من حالة النظام باللغة العربية.")

        self.assertEqual(result.status, "completed")
        messages = store.get_session_messages(result.session_id)
        self.assertEqual(messages[0]["content"], "تحقق من حالة النظام باللغة العربية.")
        self.assertEqual(result.response, "اختبار عربي ناجح")


if __name__ == "__main__":
    unittest.main(verbosity=2)
