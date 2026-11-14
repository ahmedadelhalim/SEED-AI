import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from runtime.skills.parser import SkillParser, SkillValidationError
from runtime.skills.installer import SkillLifecycleManager
from memory import store


class Phase3ASkillEngineTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.skills_root = Path(self.tmp_dir.name) / "skills"
        self.skills_root.mkdir()

        self.db_file = Path(self.tmp_dir.name) / "test_skills.sqlite"
        self.db_patch = patch.object(store, "DB_PATH", self.db_file)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def create_skill_bundle(self, name: str, version: str, custom_yaml: str = "") -> Path:
        skill_dir = self.skills_root / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        yaml_content = f"""---
name: "{name}"
version: "{version}"
description: "Test skill bundle for Phase 3A."
permissions:
  - action: "read"
    scope: "workspace"
tools:
  - name: "test_tool"
    description: "A test tool"
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
# Documentation body
"""
        if custom_yaml:
            yaml_content = custom_yaml

        (skill_dir / "SKILL.md").write_text(yaml_content, encoding="utf-8")
        return skill_dir

    def test_valid_manifest_parsing_and_stable_hashing(self):
        skill_dir = self.create_skill_bundle("my_skill", "1.0.0")
        bundle = SkillParser.parse_skill_bundle(skill_dir)

        self.assertEqual(bundle["status"], "success")
        self.assertEqual(bundle["manifest"]["name"], "my_skill")
        self.assertEqual(bundle["manifest"]["version"], "1.0.0")
        self.assertTrue(isinstance(bundle["artifact_digest"], str))
        self.assertEqual(len(bundle["artifact_digest"]), 64)

        # Hash stability
        bundle_again = SkillParser.parse_skill_bundle(skill_dir)
        self.assertEqual(bundle["artifact_digest"], bundle_again["artifact_digest"])

    def test_malformed_manifest_rejection(self):
        skill_dir = self.skills_root / "bad_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("No frontmatter here", encoding="utf-8")

        with self.assertRaises(SkillValidationError):
            SkillParser.parse_skill_bundle(skill_dir)

    def test_path_traversal_and_symlink_defense(self):
        skill_dir = self.skills_root / "traversal_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: "traversal_skill"
version: "1.0.0"
description: "Traversal test"
permissions: []
tools: []
---
""", encoding="utf-8")

        symlink_path = skill_dir / "bad_link"
        try:
            symlink_path.symlink_to(self.skills_root)
        except OSError:
            self.skipTest("Symlink creation requires elevated privileges on Windows")

        with self.assertRaises(SkillValidationError):
            SkillParser.parse_skill_bundle(skill_dir)

    def test_discovery_and_lifecycle_states(self):
        self.create_skill_bundle("skill_one", "1.0.0")
        self.create_skill_bundle("skill_two", "2.1.0")

        discovered = SkillLifecycleManager.discover_skills(self.skills_root)
        self.assertEqual(len(discovered), 2)

        record = SkillLifecycleManager.get_skill("skill_one@1.0.0")
        self.assertIsNotNone(record)
        self.assertEqual(record["state"], "Validated")
        self.assertFalse(record["reviewer_id"]) # Manual review not bypassed

    def test_manual_approval_not_bypassed(self):
        self.create_skill_bundle("secure_skill", "1.0.0")
        SkillLifecycleManager.discover_skills(self.skills_root)

        record = SkillLifecycleManager.get_skill("secure_skill@1.0.0")
        # Ensure skill is NOT active or installed by default without admin approval
        self.assertNotEqual(record["state"], "AdminApproved")
        self.assertNotEqual(record["state"], "Activated")
