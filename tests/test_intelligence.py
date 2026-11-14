import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.intelligence import (
    AdaptiveCommunicator,
    ContextAssembler,
    ExecutionVerifier,
    IntentClassifier,
    IntentType,
    VerificationOutcome,
)
from core.diagnostics import SystemDiagnostics
from memory import store


class IntelligenceArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_patch = patch.object(store, "DB_PATH", Path(self.tmp.name) / "intel.sqlite")
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        store.initialize()

    def test_intent_classification(self):
        self.assertEqual(IntentClassifier.classify("Create a detailed plan for migration"), IntentType.PLANNING)
        self.assertEqual(IntentClassifier.classify("Run workspace list tool"), IntentType.EXECUTION)
        self.assertEqual(IntentClassifier.classify("Research system architecture"), IntentType.RESEARCH)
        self.assertEqual(IntentClassifier.classify("Hello SEED greetings"), IntentType.CONVERSATION)

    def test_context_assembly(self):
        store.save_memory("project_context", "tech", "Python & SQLite", project_id="test-proj", approved=True)
        context = ContextAssembler.assemble("Tell me about tech stack", project_id="test-proj")
        self.assertEqual(context["intent"], IntentType.QUESTION.value)
        self.assertTrue(len(context["memories"]) > 0)

    def test_execution_verification(self):
        success_results = ({"status": "success", "result": "ok"},)
        fail_results = ({"status": "denied", "reason": "unauthorized"},)
        
        self.assertEqual(ExecutionVerifier.verify(success_results, "Done", "task"), VerificationOutcome.SUCCESS)
        self.assertEqual(ExecutionVerifier.verify(fail_results, "", "task"), VerificationOutcome.FAILURE)
        self.assertEqual(ExecutionVerifier.verify((), "", ""), VerificationOutcome.FAILURE)

    def test_adaptive_communicator(self):
        msg = AdaptiveCommunicator.format_response("Task completed.", IntentType.EXECUTION, VerificationOutcome.SUCCESS)
        self.assertEqual(msg, "Task completed.")
        msg_fail = AdaptiveCommunicator.format_response("Error occurred.", IntentType.EXECUTION, VerificationOutcome.FAILURE)
        self.assertIn("Notice", msg_fail)

    def test_system_diagnostics(self):
        report = SystemDiagnostics.inspect_system()
        self.assertTrue(report["database_health"])
        self.assertTrue(report["memory_available"])

    def test_evidence_verification(self):
        test_file = Path(self.tmp.name) / "evidence.txt"
        test_file.write_text("ok")
        self.assertEqual(ExecutionVerifier.verify((), "", "task", file_path=str(test_file)), VerificationOutcome.SUCCESS)
        self.assertEqual(ExecutionVerifier.verify((), "", "task", file_path=str(Path(self.tmp.name) / "missing.txt")), VerificationOutcome.FAILURE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
