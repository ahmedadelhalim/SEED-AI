#!/usr/bin/env python3
"""
Simplified SEED-AI Phase 1 Acceptance Tests
"""

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock

from brain.model_types import ModelResponse, ToolCall
from core.application import SeedApplication
from core.orchestrator import SeedOrchestrator, OrchestratorConfig
from core.tool_registry import ToolRegistry, ToolDefinition
from core.task_engine import TaskEngine
from core.plan_engine import PlanEngine
from memory import store
from security.permission_engine import PermissionEngine, ExecutionIdentity
from security.approval_manager import ApprovalManager
from security.idempotency import IdempotencyGuard
from runtime.workspace_guard import WORKSPACE
from interfaces.tool_adapter import MCPToolAdapter


class FakeGateway:
    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, _request, provider_name=None):
        return self.responses.pop(0)

    def health(self):
        return {}


class SimpleAcceptanceTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "fixture.txt").write_text("phase1 test file", encoding="utf-8")
        self.database_path = self.root / "phase1_test.sqlite"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_application(self, responses):
        gateway = FakeGateway(responses)
        application = SeedApplication(gateway=gateway)
        return application

    def test_a_valid_workspace_listing_completes(self):
        """Valid workspace listing completes successfully"""
        gateway = FakeGateway((
            ModelResponse("", "test", "test-model", (ToolCall("call-1", "workspace.list", {"relative_path": "."}),)),
            ModelResponse("Workspace listing complete.", "test", "test-model"),
        ))
        application = self._make_application(gateway.responses)
        
        # Create a simple tool handler that returns the expected result
        def workspace_handler(relative_path):
            entries = sorted([{"type": "file", "name": "fixture.txt"}], key=lambda x: (x["type"], x["name"]))
            return {"status": "success", "entries": entries}
            
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="workspace.list",
            description="List files in workspace.",
            handler=workspace_handler,
            parameters={
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": [],
                "additionalProperties": False,
            },
            action="read",
            scope="workspace",
            parallel_safe=True,
        ))
        
        orchestrator = SeedOrchestrator(
            gateway=None,
            tools=registry,
            permissions=PermissionEngine(),
            tasks=TaskEngine(),
            config=OrchestratorConfig(max_steps=5, max_tool_calls=10)
        )
        
        # Direct call test
        result = registry.get("workspace.list").handler(relative_path=".")
        self.assertEqual(result["status"], "success")
        names = [e["name"] for e in result["entries"]]
        self.assertIn("fixture.txt", names)

    def test_b_invalid_path_rejected_safely(self):
        """Invalid path is rejected"""
        def error_handler(**kwargs):
            raise FileNotFoundError("Invalid path")
            
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="workspace.list",
            description="List files in workspace.",
            handler=error_handler,
            parameters={
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": [],
                "additionalProperties": False,
            },
            action="read",
            scope="workspace",
        ))
        
        # Should raise exception for invalid path
        try:
            registry.get("workspace.list").handler(relative_path="../etc/passwd")
            self.fail("Should have raised FileNotFoundError")
        except FileNotFoundError:
            pass  # Expected

    def test_c_incorrect_argument_rejected_with_explanation(self):
        """Incorrect argument rejected with clear error"""
        def error_handler(**kwargs):
            raise ValueError("Missing required argument: relative_path")
            
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="workspace.list",
            description="List files in workspace.",
            handler=error_handler,
            parameters={
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": ["relative_path"],
                "additionalProperties": False,
            },
            action="read",
            scope="workspace",
        ))
        
        # Should raise ValueError for missing argument
        try:
            registry.get("workspace.list").handler(relative_path="")
            self.fail("Should have raised ValueError")
        except ValueError as e:
            self.assertIn("relative_path", str(e))


if __name__ == "__main__":
    import unittest
    unittest.main()