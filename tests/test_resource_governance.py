import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from brain.model_types import ModelResponse, ToolCall
from core.orchestrator import OrchestratorConfig, SeedOrchestrator
from core.resource_registry import ResourceRegistry
from core.task_engine import TaskEngine
from core.tool_registry import ToolDefinition, ToolRegistry
from memory import store
from security.permission_engine import ExecutionIdentity, PermissionEngine


class ResourceGovernanceTests(TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.database_path = Path(temporary_directory.name) / "governance.sqlite"
        patcher = patch.object(store, "DB_PATH", self.database_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tasks = TaskEngine()
        self.resources = ResourceRegistry()

    @staticmethod
    def resource_tool(handler):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="resource.access",
            description="Access registered resource.",
            handler=handler,
            parameters={
                "type": "object",
                "properties": {
                    "resource": {"type": "string"},
                    "action_type": {"type": "string"}
                },
                "required": ["resource"],
                "additionalProperties": False,
            },
            action="read",
            scope="workspace",
        ))
        return registry

    def test_registered_and_authorized_resource_succeeds(self):
        self.resources.register_resource(
            resource_id="res-valid-1",
            resource_type="database",
            name="Test DB",
            path_or_uri="sqlite://test.db",
            metadata={"project_id": "proj-1"}
        )
        PermissionEngine.TOOL_POLICIES["resource.access"] = {
            "action": "read", "scope": "workspace", "allowed": True, "approval": False
        }

        call = ToolCall("call-1", "resource.access", {"resource": "res-valid-1"})
        gateway = FakeGateway((
            ModelResponse("", "fake", "model", (call,)),
            ModelResponse("Access granted.", "fake", "model"),
        ))
        invoked = []
        orchestrator = SeedOrchestrator(
            gateway, self.resource_tool(lambda **kw: invoked.append(kw) or "ok"),
            PermissionEngine(), self.tasks
        )
        identity = ExecutionIdentity(project_id="proj-1")

        result = orchestrator.run("Access valid resource", identity=identity)
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(invoked), 1)

    def test_unregistered_resource_is_denied_and_handler_never_invoked(self):
        PermissionEngine.TOOL_POLICIES["resource.access"] = {
            "action": "read", "scope": "workspace", "allowed": True, "approval": False
        }

        call = ToolCall("call-2", "resource.access", {"resource": "res-missing"})
        gateway = FakeGateway((
            ModelResponse("", "fake", "model", (call,)),
        ))
        invoked = []
        orchestrator = SeedOrchestrator(
            gateway, self.resource_tool(lambda **kw: invoked.append(kw) or "ok"),
            PermissionEngine(), self.tasks
        )

        result = orchestrator.run("Access missing resource")
        self.assertEqual(result.status, "failed") # Orchestrator recorded denial and stopped task as failed
        self.assertEqual(len(invoked), 0)
        self.assertEqual(result.tool_results[0]["status"], "denied")
        self.assertIn("unregistered", result.tool_results[0]["reason"])

    def test_disabled_resource_is_denied(self):
        self.resources.register_resource(
            resource_id="res-disabled",
            resource_type="database",
            name="Disabled DB",
            path_or_uri="sqlite://disabled.db",
        )
        self.resources.set_resource_status("res-disabled", "disabled")
        PermissionEngine.TOOL_POLICIES["resource.access"] = {
            "action": "read", "scope": "workspace", "allowed": True, "approval": False
        }

        call = ToolCall("call-3", "resource.access", {"resource": "res-disabled"})
        gateway = FakeGateway((ModelResponse("", "fake", "model", (call,)),))
        invoked = []
        orchestrator = SeedOrchestrator(
            gateway, self.resource_tool(lambda **kw: invoked.append(kw) or "ok"),
            PermissionEngine(), self.tasks
        )

        result = orchestrator.run("Access disabled resource")
        self.assertEqual(result.tool_results[0]["status"], "denied")
        self.assertIn("status is 'disabled'", result.tool_results[0]["reason"])
        self.assertEqual(len(invoked), 0)

    def test_cross_resource_isolation_is_enforced(self):
        self.resources.register_resource(
            resource_id="res-proj2",
            resource_type="database",
            name="Other Project DB",
            path_or_uri="sqlite://proj2.db",
            metadata={"project_id": "proj-2"}
        )
        PermissionEngine.TOOL_POLICIES["resource.access"] = {
            "action": "read", "scope": "workspace", "allowed": True, "approval": False
        }

        call = ToolCall("call-4", "resource.access", {"resource": "res-proj2"})
        gateway = FakeGateway((ModelResponse("", "fake", "model", (call,)),))
        invoked = []
        orchestrator = SeedOrchestrator(
            gateway, self.resource_tool(lambda **kw: invoked.append(kw) or "ok"),
            PermissionEngine(), self.tasks
        )
        identity = ExecutionIdentity(project_id="proj-1")

        result = orchestrator.run("Access isolated resource", identity=identity)
        self.assertEqual(result.tool_results[0]["status"], "denied")
        self.assertIn("Cross-resource isolation violation", result.tool_results[0]["reason"])
        self.assertEqual(len(invoked), 0)

    def test_missing_resource_identity_for_resource_scope_is_denied(self):
        PermissionEngine.TOOL_POLICIES["resource.scoped"] = {
            "action": "read", "scope": "resource", "allowed": False, "approval": False
        }
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="resource.scoped",
            description="Resource scoped tool.",
            handler=lambda **kw: "ok",
            parameters={"type": "object", "properties": {}, "required": []},
            action="read",
            scope="resource",
        ))
        call = ToolCall("call-5", "resource.scoped", {})
        gateway = FakeGateway((ModelResponse("", "fake", "model", (call,)),))
        invoked = []
        orchestrator = SeedOrchestrator(
            gateway, registry, PermissionEngine(), self.tasks
        )
        result = orchestrator.run("Access without resource ID")
        self.assertEqual(result.tool_results[0]["status"], "denied")
        self.assertIn("denied by policy", result.tool_results[0]["reason"])


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


if __name__ == "__main__":
    import unittest
    unittest.main()
