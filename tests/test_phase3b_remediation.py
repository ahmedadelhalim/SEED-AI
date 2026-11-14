import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from runtime.skills.parser import SkillParser, SkillValidationError
from runtime.skills.installer import SkillLifecycleManager
from runtime.skills.reviewer import AdminSkillReviewer
from security.approval_manager import ApprovalManager
from security.permission_engine import ExecutionIdentity
from memory import store


class Phase3BRemediationTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.skills_root = Path(self.tmp_dir.name) / "skills"
        self.skills_root.mkdir()

        self.db_file = Path(self.tmp_dir.name) / "test_remediation.sqlite"
        self.db_patch = patch.object(store, "DB_PATH", self.db_file)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

        SkillLifecycleManager.initialize_schema()
        self.approval_manager = ApprovalManager(repository=store)

    def create_skill(self, name: str, version: str) -> Path:
        skill_dir = self.skills_root / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"""---
name: "{name}"
version: "{version}"
description: "Remediation test skill."
permissions:
  - action: "read"
    scope: "workspace"
tools: []
---
""", encoding="utf-8")
        return skill_dir

    def test_unauthenticated_reviewer_rejected(self):
        self.create_skill("auth_test", "1.0.0")
        SkillLifecycleManager.discover_skills(self.skills_root)

        unauth_id = ExecutionIdentity(principal_id="", kind="user")
        with self.assertRaises(ValueError):
            AdminSkillReviewer.request_review_approval("auth_test@1.0.0", self.approval_manager, unauth_id)

    def test_unauthorized_role_rejected(self):
        self.create_skill("role_test", "1.0.0")
        SkillLifecycleManager.discover_skills(self.skills_root)

        user_id = ExecutionIdentity(principal_id="alice", kind="user")
        with self.assertRaises(ValueError):
            AdminSkillReviewer.request_review_approval("role_test@1.0.0", self.approval_manager, user_id)

    def test_full_central_approval_staging_flow(self):
        self.create_skill("approved_flow", "1.0.0")
        SkillLifecycleManager.discover_skills(self.skills_root)

        admin_id = ExecutionIdentity(principal_id="admin-1", kind="admin")
        req_res = AdminSkillReviewer.request_review_approval("approved_flow@1.0.0", self.approval_manager, admin_id)
        approval_id = req_res["approval_id"]

        # Approve in ApprovalManager first
        self.approval_manager.approve(approval_id, approved_by="admin-1")

        # Review and approve via AdminSkillReviewer (consumes ApprovalManager token and stages artifact)
        review_res = AdminSkillReviewer.review_and_approve(
            "approved_flow@1.0.0", approval_id, admin_id, self.approval_manager, "approve", "Looks secure"
        )
        self.assertEqual(review_res["state"], "AdminApproved")
        self.assertTrue(Path(review_res["staged_path"]).exists())

        # Install skill
        install_res = AdminSkillReviewer.install_skill("approved_flow@1.0.0", admin_id)
        self.assertEqual(install_res["state"], "Installed")

        # Activate skill
        activate_res = AdminSkillReviewer.activate_skill("approved_flow@1.0.0", admin_id)
        self.assertEqual(activate_res["state"], "Activated")

    def test_approval_replay_rejected(self):
        self.create_skill("replay_test", "1.0.0")
        SkillLifecycleManager.discover_skills(self.skills_root)

        admin_id = ExecutionIdentity(principal_id="admin-1", kind="admin")
        req_res = AdminSkillReviewer.request_review_approval("replay_test@1.0.0", self.approval_manager, admin_id)
        approval_id = req_res["approval_id"]

        self.approval_manager.approve(approval_id, approved_by="admin-1")

        # First consumption succeeds
        AdminSkillReviewer.review_and_approve(
            "replay_test@1.0.0", approval_id, admin_id, self.approval_manager, "approve", "First use"
        )

        # Second consumption (replay) must fail
        # Reset state back to ReviewRequested to test replay of consumed approval token
        with store.connect() as db:
            db.execute("UPDATE skills_registry SET state = 'ReviewRequested' WHERE skill_id = 'replay_test@1.0.0'")

        with self.assertRaises(ValueError):
            AdminSkillReviewer.review_and_approve(
                "replay_test@1.0.0", approval_id, admin_id, self.approval_manager, "approve", "Replay attempt"
            )
