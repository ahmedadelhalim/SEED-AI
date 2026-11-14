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


class Phase3C1HardeningTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.skills_root = Path(self.tmp_dir.name) / "skills"
        self.skills_root.mkdir()

        self.db_file = Path(self.tmp_dir.name) / "test_phase3c1.sqlite"
        self.db_patch = patch.object(store, "DB_PATH", self.db_file)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

        SkillLifecycleManager.initialize_schema()
        GovernedDynamicToolRegistry.initialize_schema()

        self.tool_registry = ToolRegistry()
        self.permission_engine = PermissionEngine()

    def create_skill(self, name: str, version: str, tool_name: str = "custom_tool") -> Path:
        skill_dir = self.skills_root / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"""---
name: "{name}"
version: "{version}"
description: "Phase 3C.1 test skill."
permissions:
  - action: "read"
    scope: "workspace"
tools:
  - name: "{tool_name}"
    description: "Custom test tool"
    parameters:
      type: "object"
      properties:
        arg: {{"type": "string"}}
      required: ["arg"]
      additionalProperties: false
    action: "read"
    scope: "workspace"
    parallel_safe: true
---
""", encoding="utf-8")
        return skill_dir

    def test_protected_static_policy_overwrite_rejected(self):
        with self.assertRaises(PermissionError):
            self.permission_engine.register_policy(
                tool="workspace.list",
                action="read",
                scope="workspace",
            )

    def test_invalid_policy_action_rejected(self):
        with self.assertRaises(ValueError):
            self.permission_engine.register_policy(
                tool="custom.tool",
                action="invalid_action",
                scope="workspace",
            )

    def test_startup_recovery_restores_valid_tools(self):
        self.create_skill("recovery_skill", "1.0.0", tool_name="recovered.tool")
        SkillLifecycleManager.discover_skills(self.skills_root)

        admin_id = ExecutionIdentity(principal_id="admin-1", kind="admin")
        from security.approval_manager import ApprovalManager
        approval_manager = ApprovalManager(repository=store)
        req_res = AdminSkillReviewer.request_review_approval("recovery_skill@1.0.0", approval_manager, admin_id)
        approval_manager.approve(req_res["approval_id"], approved_by="admin-1")
        AdminSkillReviewer.review_and_approve("recovery_skill@1.0.0", req_res["approval_id"], admin_id, approval_manager, "approve", "OK")
        AdminSkillReviewer.install_skill("recovery_skill@1.0.0", admin_id)

        # Register tools initially
        GovernedDynamicToolRegistry.register_approved_skill_tools(
            "recovery_skill@1.0.0", self.tool_registry, self.permission_engine
        )
        self.assertIn("recovered.tool", self.tool_registry)

        # Create fresh registries simulating restart
        new_tool_registry = ToolRegistry()
        new_permission_engine = PermissionEngine()

        recovered = GovernedDynamicToolRegistry.recover_approved_tools_on_startup(
            new_tool_registry, new_permission_engine
        )

        self.assertIn("recovered.tool", recovered)
        self.assertIn("recovered.tool", new_tool_registry)
        self.assertIn("recovered.tool", new_permission_engine.TOOL_POLICIES)
