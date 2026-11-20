import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from core.application import SeedApplication
from memory import store
from brain.model_types import ModelResponse, ToolCall


class FakeProvider:
    def __init__(self, n_ctx=8192, max_tokens=64, ready=True):
        self.n_ctx = n_ctx
        self.max_tokens = max_tokens
        self._ready = ready

    def is_ready(self):
        return self._ready

    def count_chat_tokens(self, messages, tools=None):
        return len(messages) * 10 + (50 if tools else 0)


class FakeGateway:
    def __init__(self, responses, provider=None):
        self.responses = list(responses)
        self.requests = []
        self.default_provider = "fake"
        self._provider = provider or FakeProvider()

    def complete(self, request, provider_name=None):
        self.requests.append(request)
        return self.responses.pop(0)

    def get_provider(self, name):
        return self._provider


class Phase2A1IntegrationTests(TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.database_path = Path(temporary_directory.name) / "phase2a1.sqlite"
        patcher = patch.object(store, "DB_PATH", self.database_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_all_five_windows_discovery_tools_registered_in_seed_application(self):
        app = SeedApplication()
        tool_names = [
            "system.windows_host",
            "system.windows_cpu_memory",
            "system.windows_disk_volumes",
            "system.windows_processes",
            "system.windows_network",
        ]
        for name in tool_names:
            self.assertIn(name, app.tools)
            tool = app.tools.get(name)
            self.assertEqual(tool.action, "read")
            self.assertEqual(tool.scope, "system")

    def test_windows_host_tool_invocation_through_seed_request(self):
        tool_call = ToolCall("call-1", "system.windows_host", {})
        gateway = FakeGateway((
            ModelResponse("", "fake", "model", (tool_call,)),
            ModelResponse("Host info collected.", "fake", "model"),
        ))
        app = SeedApplication(gateway=gateway)

        result = app.seed_request("Get windows host info")

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.response, "Host info collected.")

        # Verify audit event and task record
        task_id = result.task_id
        task = store.get_task(task_id)
        self.assertEqual(task["status"], "completed")

        with store.connect() as database:
            events = database.execute(
                "SELECT event_type FROM events WHERE task_id = ? ORDER BY id",
                (task_id,),
            ).fetchall()
        event_types = [row["event_type"] for row in events]
        self.assertIn("tool_completed", event_types)

    def test_windows_discovery_permission_denial(self):
        tool_call = ToolCall("call-2", "system.windows_host", {})
        gateway = FakeGateway((
            ModelResponse("", "fake", "model", (tool_call,)),
            ModelResponse("Denied.", "fake", "model"),
        ))
        app = SeedApplication(gateway=gateway)

        # Force permission denial by mocking permission engine check
        with patch.object(app.permissions, "check") as mock_check:
            from security.permission_engine import PermissionDecision
            mock_check.return_value = PermissionDecision(False, False, "Explicitly denied", None)
            result = app.seed_request("Get host info")

        self.assertEqual(result.status, "completed")
        self.assertIn("tool_denied", [row["event_type"] for row in store.get_task_events(result.task_id)])
