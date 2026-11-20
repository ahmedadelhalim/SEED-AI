import tempfile
from threading import Barrier
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from brain.model_types import ModelResponse, ToolCall
from core.orchestrator import (
    CancellationToken,
    OrchestratorConfig,
    SeedOrchestrator,
)
from core.task_engine import TaskEngine
from core.tool_registry import ToolDefinition, ToolRegistry
from memory import store
from security.approval_manager import ApprovalManager
from security.permission_engine import ExecutionIdentity, PermissionEngine


class FakeProvider:
    def __init__(self, n_ctx=8192, max_tokens=64, ready=True, tools_count_fn=None):
        self.n_ctx = n_ctx
        self.max_tokens = max_tokens
        self._ready = ready
        self._tools_count_fn = tools_count_fn or (lambda msgs, tools=None: sum(len(str(m)) for m in msgs) // 4 + (100 if tools else 0))
        self.chat_called = False

    def is_ready(self):
        return self._ready

    def count_chat_tokens(self, messages, tools=None):
        return self._tools_count_fn(messages, tools)


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


class OrchestratorTests(TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.database_path = Path(temporary_directory.name) / "orchestrator.sqlite"
        patcher = patch.object(store, "DB_PATH", self.database_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tasks = TaskEngine()

    @staticmethod
    def workspace_tool(handler, parallel_safe=False):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="workspace.list",
            description="List authorized workspace entries.",
            handler=handler,
            parameters={
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": ["relative_path"],
                "additionalProperties": False,
            },
            action="read",
            scope="workspace",
            parallel_safe=parallel_safe,
        ))
        return registry

    def events_for(self, task_id):
        with store.connect() as database:
            rows = database.execute(
                "SELECT event_type FROM events WHERE task_id = ? ORDER BY id",
                (task_id,),
            ).fetchall()
        return tuple(row["event_type"] for row in rows)

    def test_orchestrator_executes_registered_tool_then_returns_final_answer(self):
        tool_call = ToolCall("call-1", "workspace.list", {"relative_path": "."})
        gateway = FakeGateway((
            ModelResponse("", "fake", "model", (tool_call,)),
            ModelResponse("Workspace listed.", "fake", "model"),
        ))
        executed = []
        registry = self.workspace_tool(lambda relative_path: executed.append(relative_path) or ["a.py"])
        orchestrator = SeedOrchestrator(
            gateway, registry, PermissionEngine(), self.tasks
        )

        result = orchestrator.run("List the workspace")

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.response, "Workspace listed.")
        self.assertEqual(executed, ["."])
        self.assertEqual(result.steps, 2)
        self.assertEqual(gateway.requests[1].messages[-1]["role"], "tool")
        self.assertIn("tool_completed", self.events_for(result.task_id))
        persisted_messages = store.get_session_messages(result.session_id)
        self.assertEqual(
            [message["role"] for message in persisted_messages],
            ["user", "assistant", "tool", "assistant"],
        )
        task = store.get_task(result.task_id)
        self.assertEqual(task["status"], "completed")

    def test_unregistered_tool_is_never_executed(self):
        call = ToolCall("call-unknown", "system.command", {"command": "anything"})
        gateway = FakeGateway((
            ModelResponse("", "fake", "model", (call,)),
            ModelResponse("I cannot run that.", "fake", "model"),
        ))
        invoked = []
        orchestrator = SeedOrchestrator(
            gateway,
            self.workspace_tool(lambda **kwargs: invoked.append(kwargs)),
            PermissionEngine(),
            self.tasks,
        )

        result = orchestrator.run("Run a command")

        self.assertEqual(result.status, "completed")
        self.assertEqual(invoked, [])
        self.assertIn("tool_denied", self.events_for(result.task_id))

    def test_tool_schema_is_checked_before_authorization_or_execution(self):
        call = ToolCall(
            "call-invalid", "workspace.list",
            {"relative_path": ".", "extra": "not allowed"},
        )
        gateway = FakeGateway((
            ModelResponse("", "fake", "model", (call,)),
            ModelResponse("Invalid request rejected.", "fake", "model"),
        ))
        invoked = []
        orchestrator = SeedOrchestrator(
            gateway,
            self.workspace_tool(lambda **kwargs: invoked.append(kwargs)),
            PermissionEngine(),
            self.tasks,
        )

        result = orchestrator.run("List the workspace")

        self.assertEqual(result.status, "completed")
        self.assertEqual(invoked, [])
        self.assertIn("tool_rejected", self.events_for(result.task_id))

    def test_permission_approval_request_does_not_execute_tool(self):
        call = ToolCall("call-approval", "workspace.list", {"relative_path": "."})
        gateway = FakeGateway((ModelResponse("", "fake", "model", (call,)),))
        invoked = []
        permissions = PermissionEngine()
        approval_policy = {
            "action": "read",
            "scope": "workspace",
            "allowed": True,
            "approval": True,
        }
        with patch.dict(
            PermissionEngine.TOOL_POLICIES,
            {"workspace.list": approval_policy},
            clear=True,
        ):
            orchestrator = SeedOrchestrator(
                gateway,
                self.workspace_tool(lambda **kwargs: invoked.append(kwargs)),
                permissions,
                self.tasks,
            )
            result = orchestrator.run("List the workspace")

        self.assertEqual(result.status, "approval_required")
        self.assertEqual(len(result.pending_approvals), 1)
        self.assertEqual(invoked, [])
        self.assertIn("approval_required", self.events_for(result.task_id))

    def test_explicit_approval_allows_only_the_exact_registered_action(self):
        call = ToolCall("call-approval", "workspace.list", {"relative_path": "."})
        gateway = FakeGateway((
            ModelResponse("", "fake", "model", (call,)),
            ModelResponse("", "fake", "model", (call,)),
            ModelResponse("Approved action completed.", "fake", "model"),
        ))
        invoked = []
        approvals = ApprovalManager()
        orchestrator = SeedOrchestrator(
            gateway,
            self.workspace_tool(lambda **kwargs: invoked.append(kwargs) or ["entry"]),
            PermissionEngine(),
            self.tasks,
            approvals=approvals,
        )
        approval_policy = {
            "action": "read",
            "scope": "workspace",
            "allowed": True,
            "approval": True,
        }

        with patch.dict(
            PermissionEngine.TOOL_POLICIES,
            {"workspace.list": approval_policy},
        ):
            pending = orchestrator.run("List the workspace")
            approval_id = pending.pending_approvals[0]["approval_id"]
            approvals.approve(approval_id, "reviewer")
            completed = orchestrator.run(
                "List the workspace", approval_id=approval_id
            )

        self.assertEqual(pending.status, "approval_required")
        self.assertEqual(completed.status, "completed")
        self.assertEqual(invoked, [{"relative_path": "."}])

    def test_idempotency_key_prevents_duplicate_tool_execution(self):
        call = ToolCall("same-call", "workspace.list", {"relative_path": "."})
        gateway = FakeGateway((
            ModelResponse("", "fake", "model", (call,)),
            ModelResponse("Done.", "fake", "model"),
            ModelResponse("", "fake", "model", (call,)),
            ModelResponse("Done.", "fake", "model"),
        ))
        invoked = []
        orchestrator = SeedOrchestrator(
            gateway,
            self.workspace_tool(lambda **kwargs: invoked.append(kwargs) or ["entry"]),
            PermissionEngine(),
            self.tasks,
        )

        first = orchestrator.run("List the workspace", idempotency_key="request-1")
        second = orchestrator.run("List the workspace", idempotency_key="request-1")

        self.assertEqual(first.status, "completed")
        self.assertEqual(second.status, "completed")
        self.assertEqual(invoked, [{"relative_path": "."}])
        self.assertIn("idempotency_reused", self.events_for(second.task_id))

    def test_session_history_and_project_memory_are_retrieved(self):
        gateway = FakeGateway((
            ModelResponse("First response.", "fake", "model"),
            ModelResponse("Continuing response.", "fake", "model"),
        ))
        orchestrator = SeedOrchestrator(
            gateway,
            self.workspace_tool(lambda **kwargs: kwargs),
            PermissionEngine(),
            self.tasks,
        )
        store.save_memory(
            "project_context",
            "renderer",
            "Use the approved renderer workflow",
            project_id="project-1",
        )
        identity = ExecutionIdentity(project_id="project-1")

        first = orchestrator.run(
            "Set up renderer", session_id="session-history", identity=identity
        )
        second = orchestrator.run(
            "Continue renderer", session_id="session-history", identity=identity
        )

        second_messages = gateway.requests[1].messages
        self.assertIn("Use the approved renderer workflow", second_messages[1]["content"])
        self.assertEqual(
            [message["role"] for message in store.get_session_messages("session-history")],
            ["user", "assistant", "user", "assistant"],
        )
        with store.connect() as database:
            linked_tasks = database.execute(
                "SELECT COUNT(*) AS count FROM session_tasks WHERE session_id = ?",
                ("session-history",),
            ).fetchone()["count"]
        self.assertEqual(linked_tasks, 2)
        self.assertEqual(first.status, "completed")
        self.assertEqual(second.status, "completed")

    def test_cancelled_task_is_persisted_without_calling_the_model(self):
        gateway = FakeGateway(())
        token = CancellationToken()
        token.cancel()
        orchestrator = SeedOrchestrator(
            gateway,
            self.workspace_tool(lambda **kwargs: kwargs),
            PermissionEngine(),
            self.tasks,
        )

        result = orchestrator.run("Stop this task", cancellation=token)

        self.assertEqual(result.status, "cancelled")
        self.assertEqual(gateway.requests, [])
        self.assertEqual(store.get_task(result.task_id)["status"], "cancelled")

    def test_tool_call_budget_is_enforced_before_execution(self):
        calls = (
            ToolCall("call-1", "workspace.list", {"relative_path": "."}),
            ToolCall("call-2", "workspace.list", {"relative_path": "sub"}),
        )
        gateway = FakeGateway((ModelResponse("", "fake", "model", calls),))
        invoked = []
        orchestrator = SeedOrchestrator(
            gateway,
            self.workspace_tool(lambda **kwargs: invoked.append(kwargs)),
            PermissionEngine(),
            self.tasks,
            OrchestratorConfig(max_tool_calls=1),
        )

        result = orchestrator.run("List directories")

        self.assertEqual(result.status, "budget_exhausted")
        self.assertEqual(invoked, [])
        self.assertEqual(store.get_task(result.task_id)["status"], "failed")

    def test_explicitly_safe_reads_run_in_parallel_and_keep_result_order(self):
        calls = (
            ToolCall("duplicate-id", "workspace.list", {"relative_path": "first"}),
            ToolCall("duplicate-id", "workspace.list", {"relative_path": "second"}),
        )
        gateway = FakeGateway((
            ModelResponse("", "fake", "model", calls),
            ModelResponse("Both directories listed.", "fake", "model"),
        ))
        barrier = Barrier(2, timeout=2)

        def synchronized_handler(relative_path):
            barrier.wait()
            return relative_path

        orchestrator = SeedOrchestrator(
            gateway,
            self.workspace_tool(synchronized_handler, parallel_safe=True),
            PermissionEngine(),
            self.tasks,
            OrchestratorConfig(max_parallel_tools=2),
        )

        result = orchestrator.run("List two directories")

        self.assertEqual(result.status, "completed")
        self.assertEqual(
            [item["result"] for item in result.tool_results],
            ["first", "second"],
        )

    def test_only_explicitly_retry_safe_tools_are_retried(self):
        call = ToolCall("call-retry", "workspace.list", {"relative_path": "."})
        gateway = FakeGateway((
            ModelResponse("", "fake", "model", (call,)),
            ModelResponse("Done.", "fake", "model"),
        ))
        attempts = []

        def flaky_handler(relative_path):
            attempts.append(relative_path)
            if len(attempts) == 1:
                raise OSError("temporary failure")
            return ["ok"]

        registry = self.workspace_tool(flaky_handler)
        tool = registry.get("workspace.list")
        registry._tools[tool.name] = ToolDefinition(
            name=tool.name,
            description=tool.description,
            handler=tool.handler,
            parameters=tool.parameters,
            action=tool.action,
            scope=tool.scope,
            retry_safe=True,
            max_attempts=2,
        )
        orchestrator = SeedOrchestrator(
            gateway, registry, PermissionEngine(), self.tasks
        )

        result = orchestrator.run("List the workspace")

        self.assertEqual(result.status, "completed")
        self.assertEqual(attempts, [".", "."])


if __name__ == "__main__":
    import unittest

    unittest.main()