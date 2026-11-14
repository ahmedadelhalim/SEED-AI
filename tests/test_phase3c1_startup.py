import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from core.application import SeedApplication
from runtime.skills.installer import SkillLifecycleManager
from runtime.skills.reviewer import AdminSkillReviewer
from runtime.skills.registry import GovernedDynamicToolRegistry
from security.approval_manager import ApprovalManager
from security.permission_engine import ExecutionIdentity
from memory import store


class Phase3C1StartupIntegrationTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.skills_root = Path(self.tmp_dir.name) / "skills"
        self.skills_root.mkdir()

        self.db_file = Path(self.tmp_dir.name) / "test_startup.sqlite"
        self.db_patch = patch.object(store, "DB_PATH", self.db_file)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

        SkillLifecycleManager.initialize_schema()
        GovernedDynamicToolRegistry.initialize_schema()

    def create_skill(self, name: str, version: str, tool_name: str = "startup.tool") -> Path:
        skill_dir = self.skills_root / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"""---
name: "{name}"
version: "{version}"
description: "Startup test skill."
permissions:
  - action: "read"
    scope: "workspace"
tools:
  - name: "{tool_name}"
    description: "Startup tool"
    parameters:
      type: "object"
      properties: {{}}
      required: []
      additionalProperties: false
    action: "read"
    scope: "workspace"
    parallel_safe: true
---
""", encoding="utf-8")
        return skill_dir

    def test_seed_application_automatically_recovers_tools_on_init(self):
        self.create_skill("auto_skill", "1.0.0", tool_name="auto.tool")
        SkillLifecycleManager.discover_skills(self.skills_root)

        admin_id = ExecutionIdentity(principal_id="admin-1", kind="admin")
        approval_manager = ApprovalManager(repository=store)
        req_res = AdminSkillReviewer.request_review_approval("auto_skill@1.0.0", approval_manager, admin_id)
        approval_manager.approve(req_res["approval_id"], approved_by="admin-1")
        AdminSkillReviewer.review_and_approve("auto_skill@1.0.0", req_res["approval_id"], admin_id, approval_manager, "approve", "OK")
        AdminSkillReviewer.install_skill("auto_skill@1.0.0", admin_id)

        # Register tools once so they enter dynamic_tools_registry
        temp_app = SeedApplication()
        GovernedDynamicToolRegistry.register_approved_skill_tools("auto_skill@1.0.0", temp_app.tools, temp_app.permissions)

        # Now instantiate a brand new SeedApplication (simulating restart)
        restarted_app = SeedApplication()

        self.assertIn("auto.tool", restarted_app.tools)
        self.assertIn("auto.tool", restarted_app.permissions.TOOL_POLICIES)
