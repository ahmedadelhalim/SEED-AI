import importlib
import sys
import tempfile
import types
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from core.task_engine import TaskEngine
from memory import store
from runtime import workspace_guard
from security.permission_engine import DecisionOutcome, PermissionEngine


class FoundationTests(TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_path = Path(temporary_directory.name)
        self.workspace = self.temporary_path / "workspace"
        self.workspace.mkdir()
        self.database_path = self.temporary_path / "seed-test.sqlite"

        database_patcher = patch.object(store, "DB_PATH", self.database_path)
        workspace_patcher = patch.object(workspace_guard, "WORKSPACE", self.workspace)
        database_patcher.start()
        workspace_patcher.start()
        self.addCleanup(workspace_patcher.stop)
        self.addCleanup(database_patcher.stop)

    def test_registered_workspace_tool_enforces_permission_policy(self):
        class FakeMCPServer:
            def __init__(self, **_kwargs):
                self.tools = {}

            def add_tool(self, function, *, name, description):
                self.tools[name] = function

        mcp_package = types.ModuleType("mcp")
        mcp_package.__path__ = []
        mcp_server_module = types.ModuleType("mcp.server")
        mcp_server_module.MCPServer = FakeMCPServer
        module_name = "interfaces.seed_mcp_server"
        sys.modules.pop(module_name, None)

        with patch.dict(
            sys.modules,
            {"mcp": mcp_package, "mcp.server": mcp_server_module},
        ):
            server_module = importlib.import_module(module_name)
            try:
                tool = server_module.server.tools["workspace_list"]
                self.assertEqual(
                    server_module.get_application().operations.status()["registered_tools"], 10
                )
                with patch.dict(PermissionEngine.TOOL_POLICIES, {}, clear=True):
                    result = tool(".")
            finally:
                sys.modules.pop(module_name, None)

        self.assertEqual(result["status"], "denied")
        self.assertIn("Unknown tool", result["reason"])
        with store.connect() as database:
            event = database.execute(
                "SELECT event_type FROM events ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(event["event_type"], "tool_denied")

    def test_permission_policy_allows_only_registered_read_scope(self):
        engine = PermissionEngine()

        decision = engine.check("read", "workspace.list", "workspace")
        health_decision = engine.check("read", "system.health", "system")

        self.assertTrue(decision.allowed)
        self.assertFalse(decision.requires_approval)
        self.assertTrue(health_decision.allowed)
        self.assertFalse(health_decision.requires_approval)

    def test_permission_policy_denies_unknown_or_mismatched_requests(self):
        engine = PermissionEngine()

        decisions = (
            engine.check("read", "unknown.tool", "workspace"),
            engine.check("write", "workspace.list", "workspace"),
            engine.check("read", "workspace.list", "system"),
            engine.check("write", "system.health", "system"),
        )

        for decision in decisions:
            with self.subTest(reason=decision.reason):
                self.assertFalse(decision.allowed)
                self.assertFalse(decision.requires_approval)
                self.assertEqual(decision.outcome, DecisionOutcome.DENY)

    def test_workspace_guard_accepts_paths_inside_root(self):
        target = workspace_guard.validate_path("notes")

        self.assertEqual(target, self.workspace / "notes")

    def test_workspace_guard_rejects_traversal_and_absolute_paths(self):
        with self.assertRaises(PermissionError):
            workspace_guard.validate_path("../outside")

        with self.assertRaises(PermissionError):
            workspace_guard.validate_path(str(self.temporary_path))

    def test_workspace_guard_rejects_symlinks(self):
        repository_workspace = Path(__file__).resolve().parents[1] / "workspace"
        link = repository_workspace / "link_test" / "external"
        if not link.is_symlink():
            self.skipTest("Repository symlink fixture is unavailable")

        with patch.object(workspace_guard, "WORKSPACE", repository_workspace):
            with self.assertRaises(PermissionError):
                workspace_guard.validate_path("link_test/external")

    def test_task_and_event_persist_in_isolated_database(self):
        engine = TaskEngine()

        result = engine.submit("  isolated persistence check  ")

        self.assertEqual(result["command"], "isolated persistence check")
        self.assertEqual(result["status"], "pending")
        self.assertTrue(self.database_path.is_file())
        with store.connect() as database:
            events = database.execute(
                "SELECT event_type, details FROM events WHERE task_id = ?",
                (result["task_id"],),
            ).fetchall()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "task_created")
        self.assertEqual(events[0]["details"], "Task recorded successfully")


if __name__ == "__main__":
    import unittest

    unittest.main()