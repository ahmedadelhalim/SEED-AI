import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brain.model_types import ModelResponse
from core.application import SeedApplication
from core.live_planning import LivePlanner, LivePlanningError
from core.tool_registry import ToolDefinition, ToolRegistry
from memory import store
from runtime import workspace_guard


class Phase4LivePlanningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_patch = patch.object(store, "DB_PATH", Path(self.tmp.name) / "live-plan.sqlite")
        self.workspace_patch = patch.object(workspace_guard, "WORKSPACE", Path(self.tmp.name))
        self.db_patch.start(); self.workspace_patch.start()
        self.addCleanup(self.db_patch.stop); self.addCleanup(self.workspace_patch.stop)
        self.tools = ToolRegistry()
        self.tools.register(ToolDefinition(
            name="local.echo", description="echo", handler=lambda value: {"value": value},
            parameters={"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"], "additionalProperties": False},
            action="read", scope="workspace",
        ))

    def valid_json(self):
        return json.dumps({"objective": "Echo safely", "steps": [{
            "step_id": "one", "name": "Echo", "tool": "local.echo", "arguments": {"value": "ok"},
            "dependencies": [], "expected_result": "echoed", "verification": "result contains ok", "risk": "read",
        }]})

    def test_live_planner_validates_model_json(self):
        class Gateway:
            def complete(self, request, provider_name=None):
                return ModelResponse(self.valid, "fake", "fake")
        gateway = Gateway(); gateway.valid = self.valid_json()
        result = LivePlanner(gateway, self.tools).generate("Echo safely")
        self.assertEqual(result["contract"].steps[0].tool, "local.echo")

    def test_live_planner_retries_invalid_json_once(self):
        class Gateway:
            def __init__(self): self.calls = 0
            def complete(self, request, provider_name=None):
                self.calls += 1
                return ModelResponse("{}" if self.calls == 1 else self.valid, "fake", "fake")
        gateway = Gateway(); gateway.valid = self.valid_json()
        result = LivePlanner(gateway, self.tools, max_attempts=2).generate("Echo safely")
        self.assertEqual(result["attempts"], 2)

    def test_live_planner_rejects_invalid_after_bounded_attempts(self):
        class Gateway:
            def complete(self, request, provider_name=None):
                return ModelResponse("{", "fake", "fake")
        with self.assertRaises(LivePlanningError):
            LivePlanner(Gateway(), self.tools, max_attempts=2).generate("bad")

    def test_plan_result_verification_rejects_unknown_criteria(self):
        from core.orchestrator import SeedOrchestrator
        self.assertFalse(SeedOrchestrator._verify_plan_result({"status": "success", "result": {"value": "ok"}}, "unknown criterion"))
        self.assertTrue(SeedOrchestrator._verify_plan_result({"status": "success", "result": {"value": "ok"}}, "result contains ok"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
