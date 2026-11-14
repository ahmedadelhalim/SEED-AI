import unittest
from unittest.mock import patch
from pathlib import Path

from core.plan_engine import PlanEngine
from memory import store


class Phase41RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = self.subTest
        self.root = Path(__file__).parent / "__phase41_tmp__"
        self.root.mkdir(exist_ok=True)
        self.patch = patch.object(store, "DB_PATH", self.root / "phase41.sqlite")
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(lambda: (self.root / "phase41.sqlite").unlink(missing_ok=True))

    def test_cancel_transitions_pending_steps_without_completing_plan(self):
        engine = PlanEngine()
        plan_id = engine.create_plan("cancel", [{"step_id": "one", "name": "one"}])
        self.assertEqual(engine.cancel(plan_id), "cancelled")
        self.assertEqual(engine.status(plan_id)["steps"][0]["state"], "cancelled")

    def test_resume_returns_persisted_plan(self):
        engine = PlanEngine()
        plan_id = engine.create_plan("resume", [{"step_id": "one", "name": "one"}])
        engine.claim_step(plan_id, "one")
        resumed = engine.resume(plan_id)
        self.assertEqual(resumed["steps"][0]["state"], "pending")
        self.assertEqual(resumed["steps"][0]["result"]["recovered"], True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
