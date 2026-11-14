import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from runtime.skills.parser import SkillParser, SkillValidationError
from runtime.skills.installer import SkillLifecycleManager
from runtime.skills.reviewer import AdminSkillReviewer
from memory import store


class Phase3BSecurityTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.skills_root = Path(self.tmp_dir.name) / "skills"
        self.skills_root.mkdir()

        self.db_file = Path(self.tmp_dir.name) / "test_phase3b.sqlite"
        self.db_patch = patch.object(store, "DB_PATH", self.db_file)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

        SkillLifecycleManager.initialize_schema()

    def create_skill(self, name: str, version: str) -> Path:
        skill_dir = self.skills_root / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"""---
name: "{name}"
version: "{version}"
description: "Test skill for Phase 3B."
permissions:
  - action: "read"
    scope: "workspace"
tools: []
---
""", encoding="utf-8")
        return skill_dir

    def test_missing_reviewer_identity_rejected(self):
        self.create_skill("review_test", "1.0.0")
        SkillLifecycleManager.discover_skills(self.skills_root)

        with self.assertRaises(ValueError):
            AdminSkillReviewer.review_skill("review_test@1.0.0", "", "approve", "Looks good")

    def test_unauthorized_reviewer_or_decision(self):
        self.create_skill("decision_test", "1.0.0")
        SkillLifecycleManager.discover_skills(self.skills_root)

        with self.assertRaises(ValueError):
            AdminSkillReviewer.review_skill("decision_test@1.0.0", "admin-1", "invalid_decision", "test")

    def test_activation_before_installation_fails(self):
        self.create_skill("order_test", "1.0.0")
        SkillLifecycleManager.discover_skills(self.skills_root)
        AdminSkillReviewer.review_skill("order_test@1.0.0", "admin-1", "approve", "Approved")

        # Try to activate while state is AdminApproved (skipping Installed)
        with self.assertRaises(ValueError):
            AdminSkillReviewer.activate_skill("order_test@1.0.0", "operator-1")

    def test_complete_review_install_activate_flow(self):
        self.create_skill("full_flow", "1.0.0")
        SkillLifecycleManager.discover_skills(self.skills_root)

        # 1. Review & Approve
        res_review = AdminSkillReviewer.review_skill("full_flow@1.0.0", "admin-1", "approve", "Approved by policy")
        self.assertEqual(res_review["state"], "AdminApproved")

        # 2. Install
        res_install = AdminSkillReviewer.install_skill("full_flow@1.0.0", "operator-1")
        self.assertEqual(res_install["state"], "Installed")

        # 3. Activate
        res_activate = AdminSkillReviewer.activate_skill("full_flow@1.0.0", "operator-1")
        self.assertEqual(res_activate["state"], "Activated")

        # 4. Deactivate
        res_deactivate = AdminSkillReviewer.deactivate_skill("full_flow@1.0.0", "operator-1")
        self.assertEqual(res_deactivate["state"], "Disabled")

    def test_artifact_modification_invalidates_approval(self):
        skill_dir = self.create_skill("tamper_test", "1.0.0")
        SkillLifecycleManager.discover_skills(self.skills_root)

        AdminSkillReviewer.review_skill("tamper_test@1.0.0", "admin-1", "approve", "Approved")

        # Tamper with skill file on disk
        (skill_dir / "SKILL.md").write_text("""---
name: "tamper_test"
version: "1.0.0"
description: "Tampered content"
permissions: []
tools: []
---
""", encoding="utf-8")

        with self.assertRaises(SkillValidationError):
            AdminSkillReviewer.review_skill("tamper_test@1.0.0", "admin-1", "approve", "Re-review")
