import re
import unittest
from pathlib import Path


class GitWorkflowScriptTests(unittest.TestCase):
    def test_git_sync_script_exists(self):
        script_path = Path(r"d:\SEED-AI\scripts\git-sync.ps1")
        self.assertTrue(script_path.is_file(), "git-sync.ps1 script must exist")

    def test_git_sync_contains_safety_patterns(self):
        script_path = Path(r"d:\SEED-AI\scripts\git-sync.ps1")
        content = script_path.read_text(encoding="utf-8")
        self.assertIn(".env", content)
        self.assertIn(".db", content)
        self.assertIn("__pycache__", content)
        self.assertIn("Test-SensitiveFiles", content)
        self.assertIn("git diff --check", content)

    def test_git_sync_supports_required_modes(self):
        script_path = Path(r"d:\SEED-AI\scripts\git-sync.ps1")
        content = script_path.read_text(encoding="utf-8")
        self.assertIn("Status", content)
        self.assertIn("Check", content)
        self.assertIn("Commit", content)
        self.assertIn("Push", content)
        self.assertIn("Sync", content)


if __name__ == "__main__":
    unittest.main()
