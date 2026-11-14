import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from core.tool_registry import ToolDefinition, ToolRegistry
from security.permission_engine import PermissionEngine, ExecutionIdentity
from runtime.skills.installer import SkillLifecycleManager
from runtime.skills.reviewer import AdminSkillReviewer
from runtime.skills.registry import GovernedDynamicToolRegistry
from memory import store


class Phase3C1HardenedAtomicityTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.skills_root = Path(self.tmp_dir.name) / "skills"
        self.skills_root.mkdir()

        self.db_file = Path(self.tmp_dir.name) / "test_hardened_atomicity.sqlite"
        self.db_patch = patch.object(store, "DB_PATH", self.db_file)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

        SkillLifecycleManager.initialize_schema()
        GovernedDynamicToolRegistry.initialize_schema()

        self.tool_registry = ToolRegistry()
        self.tool_registry.register(ToolDefinition(
            name="workspace.list", description="static", handler=lambda **_: {},
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            action="read", scope="workspace",
        ))
        self.permission_engine = PermissionEngine()

    def create_skill(self, name: str, version: str, tools_yaml: str) -> Path:
        skill_dir = self.skills_root / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"""---
name: "{name}"
version: "{version}"
description: "Hardened atomicity test skill."
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

    def test_ownership_bound_removal_rejects_unowned_or_static(self):
        # Cannot remove static built-in tools
        removed = self.tool_registry.unregister_with_ownership("workspace.list", "some_skill", "fake_digest")
        self.assertFalse(removed)
        self.assertIn("workspace.list", self.tool_registry)

    def test_policy_registration_failure_triggers_atomic_rollback(self):
        tools_yaml = """  - name: "tool_one"
    description: "First tool"
    parameters:
      type: "object"
      properties: {}
      additionalProperties: false
    action: "read"
    scope: "workspace"
  - name: "tool_two"
    description: "Second tool"
    parameters:
      type: "object"
      properties: {}
      additionalProperties: false
    action: "read"
    scope: "workspace"
"""
        self.create_skill_with_tools = self.create_skill("rollback_skill", "1.0.0", tools_yaml)
        SkillLifecycleManager.discover_skills(self.skills_root)
        self.approve_and_install("rollback_skill@1.0.0")

        # Inject failure during policy registration for the second tool
        original_register_policy = self.permission_engine.register_policy
        call_count = [0]

        def flaky_register_policy(tool, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                raise PermissionError("Injected policy registration failure")
            return original_register_policy(tool, *args, **kwargs)

        with patch.object(self.permission_engine, "register_policy", side_effect=flaky_register_policy):
            with self.assertRaises(Exception):
                GovernedDynamicToolRegistry.register_approved_skill_tools(
                    "rollback_skill@1.0.0", self.tool_registry, self.permission_engine
                )

        # Verify atomic rollback removed tool_one as well
        self.assertNotIn("tool_one", self.tool_registry)
        self.assertNotIn("tool_two", self.tool_registry)
        self.assertNotIn("tool_one", self.permission_engine.TOOL_POLICIES)
