import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from core.tool_registry import ToolRegistry
from security.permission_engine import PermissionEngine, ExecutionIdentity
from runtime.skills.installer import SkillLifecycleManager
from runtime.skills.reviewer import AdminSkillReviewer
from runtime.skills.registry import GovernedDynamicToolRegistry
from memory import store


class Phase3CDynamicRegistryTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.skills_root = Path(self.tmp_dir.name) / "skills"
        self.skills_root.mkdir()

        self.db_file = Path(self.tmp_dir.name) / "test_phase3c.sqlite"
        self.db_patch = patch.object(store, "DB_PATH", self.db_file)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

        SkillLifecycleManager.initialize_schema()
        GovernedDynamicToolRegistry.initialize_schema()

        self.tool_registry = ToolRegistry()
        self.permission_engine = PermissionEngine()

    def create_skill(self, name: str, version: str, tool_name: str = "dynamic_tool") -> Path:
        skill_dir = self.skills_root / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"""---
name: "{name}"
version: "{version}"
description: "Phase 3C test skill."
permissions:
  - action: "read"
    scope: "workspace"
tools:
  - name: "{tool_name}"
    description: "A dynamic test tool"
    parameters:
      type: "object"
      properties:
        query: {{"type": "string"}}
      required: ["query"]
      additionalProperties: false
    action: "read"
    scope: "workspace"
    parallel_safe: true
---
""", encoding="utf-8")
        return skill_dir

    def test_approved_installed_skill_registers_tool(self):
        self.create_skill("tool_skill", "1.0.0", tool_name="workspace.search_index")
        SkillLifecycleManager.discover_skills(self.skills_root)

        admin_id = ExecutionIdentity(principal_id="admin-1", kind="admin")
        # Use the standard central approval flow.
        from security.approval_manager import ApprovalManager
        approval_manager = ApprovalManager(repository=store)

        req_res = AdminSkillReviewer.request_review_approval("tool_skill@1.0.0", approval_manager, admin_id)
        approval_id = req_res["approval_id"]
        approval_manager.approve(approval_id, approved_by="admin-1")
        AdminSkillReviewer.review_and_approve("tool_skill@1.0.0", approval_id, admin_id, approval_manager, "approve", "OK")
        AdminSkillReviewer.install_skill("tool_skill@1.0.0", admin_id)

        # Register dynamic tools
        registered = GovernedDynamicToolRegistry.register_approved_skill_tools(
            "tool_skill@1.0.0", self.tool_registry, self.permission_engine
        )

        self.assertIn("workspace.search_index", registered)
        self.assertIn("workspace.search_index", self.tool_registry)
        self.assertIn("workspace.search_index", self.permission_engine.TOOL_POLICIES)

        # Verify execution invokes governed execution handler returning success and recording audit
        tool_def = self.tool_registry.get("workspace.search_index")
        res = tool_def.handler(query="test")
        self.assertEqual(res["status"], "success")

    def test_unapproved_skill_cannot_register_tools(self):
        self.create_skill("unapproved_skill", "1.0.0", tool_name="bad_tool")
        SkillLifecycleManager.discover_skills(self.skills_root)

        # State is 'Validated', not 'Installed' or 'Activated'
        with self.assertRaises(ValueError):
            GovernedDynamicToolRegistry.register_approved_skill_tools(
                "unapproved_skill@1.0.0", self.tool_registry, self.permission_engine
            )

    def test_unregistration_on_revocation(self):
        self.create_skill("unreg_skill", "1.0.0", tool_name="temp_tool")
        SkillLifecycleManager.discover_skills(self.skills_root)

        admin_id = ExecutionIdentity(principal_id="admin-1", kind="admin")
        from security.approval_manager import ApprovalManager
        approval_manager = ApprovalManager(repository=store)
        req_res = AdminSkillReviewer.request_review_approval("unreg_skill@1.0.0", approval_manager, admin_id)
        approval_manager.approve(req_res["approval_id"], approved_by="admin-1")
        AdminSkillReviewer.review_and_approve("unreg_skill@1.0.0", req_res["approval_id"], admin_id, approval_manager, "approve", "OK")
        AdminSkillReviewer.install_skill("unreg_skill@1.0.0", admin_id)

        GovernedDynamicToolRegistry.register_approved_skill_tools(
            "unreg_skill@1.0.0", self.tool_registry, self.permission_engine
        )
        self.assertIn("temp_tool", self.tool_registry)

        # Unregister tools
        unregistered = GovernedDynamicToolRegistry.unregister_skill_tools(
            "unreg_skill@1.0.0", self.tool_registry, self.permission_engine
        )
        self.assertIn("temp_tool", unregistered)
        self.assertNotIn("temp_tool", self.tool_registry)
        self.assertNotIn("temp_tool", self.permission_engine.TOOL_POLICIES)
