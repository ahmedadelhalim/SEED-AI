import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from brain.model_gateway import ModelGateway
from brain.model_types import ModelCapabilities, ModelRequest, ModelResponse
from brain.providers.base import ModelProvider
from core.operations import OperationsAPI
from core.service_registry import ServiceRegistry
from core.task_engine import TaskEngine
from core.tool_registry import ToolRegistry
from memory import store


class HealthProvider(ModelProvider):
    name = "health-test"
    default_model = "test-model"

    def __init__(self):
        self.list_calls = 0

    def list_models(self):
        self.list_calls += 1
        return (self.default_model,)

    def capabilities(self, model):
        return ModelCapabilities(tool_calling=False, source="test")

    def chat(self, request: ModelRequest):
        return ModelResponse("ok", self.name, request.model or self.default_model)


class OperationsTests(TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.database_path = Path(temporary_directory.name) / "operations.sqlite"
        patcher = patch.object(store, "DB_PATH", self.database_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tasks = TaskEngine()
        self.provider = HealthProvider()
        self.gateway = ModelGateway((self.provider,), default_provider="health-test")
        self.services = ServiceRegistry()
        self.services.register("workspace", "tool", lambda: True)
        self.services.register("mcp-stdio", "integration", lambda: False)
        self.operations = OperationsAPI(
            self.gateway, ToolRegistry(), self.services
        )

    def test_status_does_not_probe_providers_without_explicit_refresh(self):
        status = self.operations.status()

        self.assertEqual(self.provider.list_calls, 0)
        self.assertEqual(status["providers"], {})
        self.assertEqual(status["registered_tools"], 0)
        self.assertEqual(status["services"]["workspace"]["status"], "unverified")

        refreshed = self.operations.provider_health(refresh=True)

        self.assertEqual(self.provider.list_calls, 1)
        self.assertTrue(refreshed["health-test"]["healthy"])
        self.assertEqual(refreshed["health-test"]["model_count"], 1)

    def test_service_registry_reports_verified_health_and_safe_errors(self):
        healthy = self.services.check("workspace")
        unhealthy = self.services.check("mcp-stdio")

        self.assertEqual(healthy.status, "healthy")
        self.assertEqual(unhealthy.status, "unhealthy")
        self.assertIsNotNone(healthy.checked_at)

    def test_active_history_audit_and_failure_queries(self):
        active = self.tasks.submit("active operation")
        failed = self.tasks.submit("failed operation")
        self.tasks.set_status(failed["task_id"], "failed")
        self.tasks.record_event(failed["task_id"], "tool_failed", "ValueError")

        status = self.operations.status()
        history = self.operations.execution_history()
        audit = self.operations.audit_history(task_id=failed["task_id"])
        failures = self.operations.failures()

        self.assertEqual(
            [task["id"] for task in status["active_tasks"]],
            [active["task_id"]],
        )
        self.assertEqual(len(history), 2)
        self.assertEqual(audit[0]["event_type"], "tool_failed")
        self.assertEqual(failures["tasks"][0]["id"], failed["task_id"])
        self.assertEqual(failures["events"][0]["event_type"], "tool_failed")

    def test_resource_snapshot_reports_disk_and_process_metrics(self):
        snapshot = self.operations.resource_snapshot()

        self.assertGreater(snapshot["disk_total_bytes"], 0)
        self.assertGreaterEqual(snapshot["disk_free_bytes"], 0)
        self.assertGreaterEqual(snapshot["process_cpu_seconds"], 0)
        self.assertGreater(snapshot["memory_total_bytes"], 0)
        self.assertGreaterEqual(snapshot["memory_available_bytes"], 0)
        self.assertGreaterEqual(snapshot["memory_used_bytes"], 0)
        self.assertGreater(snapshot["logical_processor_count"], 0)
        self.assertIn("process_max_rss_bytes", snapshot)

    def test_event_cursor_returns_ordered_safe_event_metadata(self):
        task = self.tasks.submit("event cursor test")
        self.tasks.record_event(task["task_id"], "permission_decision", "workspace.list:ALLOW")

        events = self.operations.events_after(event_id=0)

        self.assertEqual([event["event_type"] for event in events], [
            "task_created", "permission_decision",
        ])
        self.assertNotIn("details", events[0])
        self.assertEqual(events[1]["decision"], "ALLOW")
        self.assertEqual(self.operations.status()["event_cursor"], events[-1]["id"])


if __name__ == "__main__":
    import unittest

    unittest.main()