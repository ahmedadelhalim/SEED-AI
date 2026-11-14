import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from core.tool_registry import ToolRegistry, ToolError
from security.permission_engine import PermissionEngine, ExecutionIdentity
from runtime.skills.installer import SkillLifecycleManager
from runtime.skills.reviewer import AdminSkillReviewer
from runtime.skills.registry import GovernedDynamicToolRegistry
from memory import store


class Phase3C1AtomicityTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.skills_root = Path(self.tmp_dir.name) / "skills"
        self.skills_root.mkdir()

        self.db_file = Path(self.tmp_dir.name) / "test_atomicity.sqlite"
        self.db_patch = patch.object(store, "DB_PATH", self.db_file)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

        SkillLifecycleManager.initialize_schema()
        GovernedDynamicToolRegistry.initialize_schema()

        self.tool_registry = ToolRegistry()
        self.permission_engine = PermissionEngine()

    def create_skill_with_tools(self, name: str, version: str, tools_yaml: str) -> Path:
        skill_dir = self.skills_root / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"""---
name: "{name}"
version: "{version}"
description: "Atomicity test skill."
permissions:
  - action: "read"
    scope: "workspace"
tools:
{tools_yaml}
---
""", encoding="utf-8")
        return skill_dir

    def approve_and_install(self, skill_id: str):
        admin_id = ExecutionIdentity(principal_id="admin-1", kind="admin")
        from security.approval_manager import ApprovalManager
        approval_manager = ApprovalManager(repository=store)
        req_res = AdminSkillReviewer.request_review_approval(skill_id, approval_manager, admin_id)
        approval_manager.approve(req_res["approval_id"], approved_by="admin-1")
        AdminSkillReviewer.review_and_approve(skill_id, req_res["approval_id"], admin_id, approval_manager, "approve", "OK")
        AdminSkillReviewer.install_skill(skill_id, admin_id)

    def test_atomic_rollback_on_registration_failure(self):
        # Second tool has invalid schema type ('array' instead of valid object or missing params),
        # causing registration failure midway. First tool should be rolled back.
        tools_yaml = """  - name: "tool_one"
    description: "First tool"
    parameters:
      type: "object"
      properties: {}
      additionalProperties: false
    action: "read"
    scope: "workspace"
  - name: "tool_two"
    description: "Second tool with invalid parameters type"
    parameters:
      type: "invalid_type"
    action: "read"
    scope: "workspace"
"""
        self.create_skill_with_tools("atomic_skill", "1.0.0", tools_yaml)
        SkillLifecycleManager.discover_skills(self.skills_root)
        self.approve_and_install("atomic_skill@1.0.0")

        initial_tool_count = len(self.tool_registry)

        with self.assertRaises(Exception):
            GovernedDynamicToolRegistry.register_approved_skill_tools(
                "atomic_skill@1.0.0", self.tool_registry, self.permission_engine
            )

        # Verify atomic rollback: neither tool_one nor tool_two should remain registered
        self.assertEqual(len(self.tool_registry), initial_tool_count)
        self.assertNotIn("tool_one", self.tool_registry)
        self.assertNotIn("tool_two", self.tool_registry)
        self.assertNotIn("tool_one", self.permission_engine.TOOL_POLICIES)
