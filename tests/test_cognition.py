import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.cognition import CognitiveEngine
from memory import store


class CognitionEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_patch = patch.object(store, "DB_PATH", Path(self.tmp.name) / "cognition.sqlite")
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        store.initialize()

    def test_cognitive_processing_loop(self):
        result = CognitiveEngine.process_objective("Create a plan to refactor the codebase", project_id="cog-proj")
        self.assertEqual(result["intent"], "planning")
        self.assertTrue(result["requires_planning"])

        CognitiveEngine.learn_and_remember(1, "Refactor codebase", "Successfully refactored modules", project_id="cog-proj")
        memories = list(store.search_memory("Refactor", project_id="cog-proj"))
        self.assertTrue(len(memories) > 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
