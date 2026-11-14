import json
import unittest

from core.planning import PlanValidationError, PlanningContract
from core.tool_registry import ToolDefinition, ToolRegistry


class Phase3PlanningTests(unittest.TestCase):
    def setUp(self):
        self.tools = ToolRegistry()
        self.tools.register(ToolDefinition(
            name="local.echo", description="echo", handler=lambda value: {"value": value},
            parameters={"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"], "additionalProperties": False},
            action="read", scope="workspace",
        ))

    def plan(self, **overrides):
        step = {
            "step_id": "one", "name": "Echo", "tool": "local.echo",
            "arguments": {"value": "hello"}, "dependencies": [],
            "expected_result": "echoed", "verification": "result contains value", "risk": "read",
        }
        step.update(overrides.pop("step", {}))
        value = {"objective": "Run echo", "steps": [step]}
        value.update(overrides)
        return value

    def test_valid_plan_is_typed(self):
        contract = PlanningContract.from_mapping(self.plan(), self.tools)
        self.assertEqual(contract.steps[0].tool, "local.echo")

    def test_unregistered_tool_rejected(self):
        with self.assertRaises(PlanValidationError):
            PlanningContract.from_mapping(self.plan(step={"tool": "missing.tool"}), self.tools)

    def test_invalid_arguments_rejected(self):
        with self.assertRaises(PlanValidationError):
            PlanningContract.from_mapping(self.plan(step={"arguments": {"value": 42}}), self.tools)

    def test_dependency_cycle_rejected(self):
        first = self.plan()["steps"][0] | {"dependencies": ["two"]}
        second = self.plan()["steps"][0] | {"step_id": "two", "dependencies": ["one"]}
        with self.assertRaises(PlanValidationError):
            PlanningContract.from_mapping({"objective": "cycle", "steps": [first, second]}, self.tools)

    def test_three_step_plan_executes_through_governed_orchestrator_and_recovers(self):
        from core.orchestrator import SeedOrchestrator
        from core.task_engine import TaskEngine
        from security.permission_engine import PermissionEngine
        from memory import store

        calls = []
        registry = self.tools
        registry.register(ToolDefinition(
            name="local.record", description="record", handler=lambda value: calls.append(value) or {"value": value},
            parameters={"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"], "additionalProperties": False},
            action="read", scope="workspace",
        ))
        class Gateway:
            def complete(self, request, provider_name=None):
                raise AssertionError("plan execution must not request another model turn")

        tasks = TaskEngine()
        permissions = PermissionEngine()
        permissions.register_policy("local.record", "read", "workspace", skill_id="benchmark", artifact_digest="builtin")
        orchestrator = SeedOrchestrator(Gateway(), registry, permissions, tasks)
        plan_id = orchestrator.plan_engine.create_plan("Three steps", [
            {"step_id": "one", "name": "One", "tool": "local.record", "arguments": {"value": "one"}},
            {"step_id": "two", "name": "Two", "dependencies": ["one"], "tool": "local.record", "arguments": {"value": "two"}},
            {"step_id": "three", "name": "Three", "dependencies": ["two"], "tool": "local.record", "arguments": {"value": "three"}},
        ])
        # The durable PlanEngine accepts normalized metadata; execute it through SEED.
        with store.connect() as db:
            for step_id, value in (("one", "one"), ("two", "two"), ("three", "three")):
                db.execute("UPDATE plan_steps SET metadata_json = ? WHERE plan_id = ? AND step_id = ?", (json.dumps({"tool": "local.record", "arguments": {"value": value}}), plan_id, step_id))
        task_id = tasks.submit("execute three-step plan")["task_id"]
        result = orchestrator.execute_plan(plan_id, task_id)
        self.assertEqual(result["plan"]["state"], "completed")
        self.assertEqual(calls, ["one", "two", "three"])
        self.assertEqual(len(result["results"]), 3)
        events = store.get_task_events(task_id)
        self.assertEqual(len([row for row in events if row["event_type"] == "plan_step_completed"]), 3)
        resumed = orchestrator.plan_engine.resume(plan_id)
        self.assertFalse(orchestrator.plan_engine.next_steps(plan_id))
        self.assertEqual(resumed["state"], "completed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
