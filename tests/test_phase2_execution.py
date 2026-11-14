import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.plan_engine import PlanEngine
from integrations.http import HttpIntegration
from integrations.registry import Integration, IntegrationError, IntegrationRegistry
from memory import store


class Phase2ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_patch = patch.object(store, "DB_PATH", Path(self.tmp.name) / "phase2.sqlite")
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def test_plan_dependencies_persist_and_recover_without_repeating_completed_step(self):
        engine = PlanEngine()
        plan_id = engine.create_plan("Prepare report", [
            {"step_id": "collect", "name": "Collect evidence"},
            {"step_id": "summarize", "name": "Summarize", "dependencies": ["collect"]},
        ])
        self.assertEqual([step.step_id for step in engine.next_steps(plan_id)], ["collect"])
        self.assertTrue(engine.claim_step(plan_id, "collect"))
        self.assertTrue(engine.complete_step(plan_id, "collect", {"count": 2}, [{"event": "collected"}]))
        self.assertEqual([step.step_id for step in engine.next_steps(plan_id)], ["summarize"])
        self.assertTrue(engine.claim_step(plan_id, "summarize"))
        recovered = engine.resume(plan_id)
        self.assertEqual(recovered["steps"][0]["state"], "completed")
        self.assertEqual(recovered["steps"][1]["state"], "pending")
        self.assertFalse(engine.claim_step(plan_id, "collect"))

    def test_failed_step_blocks_dependents_and_plan_not_completed(self):
        engine = PlanEngine()
        plan_id = engine.create_plan("Fail safely", [
            {"step_id": "one", "name": "One"},
            {"step_id": "two", "name": "Two", "dependencies": ["one"]},
        ])
        engine.claim_step(plan_id, "one")
        engine.fail_step(plan_id, "one", {"error": "injected"}, [{"event": "failure"}])
        plan = engine.get_plan(plan_id)
        self.assertEqual(plan["state"], "failed")
        self.assertEqual(plan["steps"][1]["state"], "blocked")

    def test_http_integration_retries_and_returns_structured_result(self):
        calls = []

        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"ok": true}'

        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            return Response()

        integration = HttpIntegration("http://example.test", retries=1, opener=opener)
        result = integration.request("GET", "/health")
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["body"], {"ok": True})
        self.assertEqual(len(calls), 1)

    def test_disabled_integration_is_denied(self):
        registry = IntegrationRegistry()
        registry.register(Integration("local", "1.0", object(), "network.read"))
        registry.disable("local")
        with self.assertRaises(IntegrationError) as raised:
            registry.get("local")
        self.assertEqual(raised.exception.code, "integration_unavailable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
