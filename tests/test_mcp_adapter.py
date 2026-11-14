import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from core.task_engine import TaskEngine
from core.tool_registry import ToolDefinition, ToolRegistry
from interfaces.tool_adapter import MCPToolAdapter
from memory import store
from security.permission_engine import PermissionEngine


class MCPToolAdapterTests(TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.database_path = Path(temporary_directory.name) / "mcp.sqlite"
        patcher = patch.object(store, "DB_PATH", self.database_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tasks = TaskEngine()

    @staticmethod
    def make_registry(handler):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="workspace.list",
            description="List workspace entry names.",
            handler=handler,
            parameters={
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": ["relative_path"],
                "additionalProperties": False,
            },
            action="read",
            scope="workspace",
        ))
        return registry

    def test_adapter_authorizes_registered_tool_and_records_completion(self):
        invocations = []
        adapter = MCPToolAdapter(
            self.make_registry(
                lambda relative_path: invocations.append(relative_path)
                or {"status": "success", "entries": []}
            ),
            PermissionEngine(),
            self.tasks,
        )

        result = adapter.invoke(
            "workspace.list", {"relative_path": "."}
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(invocations, ["."])
        with store.connect() as database:
            events = database.execute(
                "SELECT event_type FROM events ORDER BY id"
            ).fetchall()
        self.assertEqual(
            [row["event_type"] for row in events],
            ["task_created", "permission_decision", "tool_completed"],
        )

    def test_adapter_denies_default_unknown_tool_before_handler(self):
        invocations = []
        adapter = MCPToolAdapter(
            self.make_registry(lambda **kwargs: invocations.append(kwargs)),
            PermissionEngine(),
            self.tasks,
        )
        with patch.dict(PermissionEngine.TOOL_POLICIES, {}, clear=True):
            result = adapter.invoke(
                "workspace.list", {"relative_path": "."}
            )

        self.assertEqual(result["status"], "denied")
        self.assertEqual(invocations, [])
        denied_events = store.list_events(event_types=("tool_denied",))
        self.assertEqual(len(denied_events), 1)

    def test_adapter_rejects_unexpected_arguments(self):
        invocations = []
        adapter = MCPToolAdapter(
            self.make_registry(lambda **kwargs: invocations.append(kwargs)),
            PermissionEngine(),
            self.tasks,
        )

        result = adapter.invoke(
            "workspace.list",
            {"relative_path": ".", "command": "do not execute"},
        )

        self.assertEqual(result["status"], "invalid_arguments")
        self.assertEqual(invocations, [])


if __name__ == "__main__":
    import unittest

    unittest.main()