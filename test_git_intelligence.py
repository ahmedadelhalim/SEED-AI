"""Test Git Intelligence subsystem import and functionality."""

import sys
sys.path.insert(0, 'D:\\SEED-AI')

from core.git_intelligence import (
    BranchManager,
    CommitIntelligence,
    GitCommit,
    PullRequestManager,
    ConflictAnalyzer,
    ProjectVersioner,
    RestorationManager,
    VersionBump,
    SemanticVersion,
    ReviewChecklist,
    ConflictAnalysis,
)

print("=== Testing Git Intelligence Subsystem ===\n")

# 1. Test BranchManager
print("1. Testing BranchManager")
bm = BranchManager()
branch_name = bm.get_branch_name("python", "2026-11-14T10-00-00Z")
assert branch_name == "modernize/python-2026-11-14T10-00-00Z", f"Expected modernize/python-2026-11-14T10-00-00Z, got {branch_name}"
print(f"   ✓ Branch name generation: {branch_name}")
bm.create_feature_branch("main")
print("   ✓ Feature branch creation")

# 2. Test CommitIntelligence
print("\n2. Testing CommitIntelligence")
ci = CommitIntelligence()
msg = ci.format_commit_message("Add new function", "REQ-123", "modernize/python-2026-11-14T10-00-00Z")
assert msg == "Add new function (from modernize/python-2026-11-14T10-00-00Z) [ticket REQ-123]", f"Unexpected message: {msg}"
print(f"   ✓ Commit message format: {msg}")
meta = ci.extract_git_metadata(msg)
assert meta["description"] == "Add new function", f"Unexpected description: {meta['description']}"
assert meta["ticket_ref"] == "REQ-123", f"Unexpected ticket_ref: {meta['ticket_ref']}"
assert meta["branch"] == "modernize/python-2026-11-14T10-00-00Z", f"Unexpected branch: {meta['branch']}"
print(f"   ✓ Commit metadata extraction: {meta}")
git_commit = ci.build_commit("Fix bug", "BUG-456", "feature/python-fix")
assert git_commit.message == "Fix bug (from feature/python-fix) [ticket BUG-456]", f"Unexpected commit message: {git_commit.message}"
assert git_commit.ticket_ref == "BUG-456"
assert git_commit.branch == "feature/python-fix"
print(f"   ✓ GitCommit building: {git_commit.message}")

# 3. Test PullRequestManager
print("\n3. Testing PullRequestManager")
pm = PullRequestManager()
pr_template = pm.create_pr_template(
    "Modernize: Python migration",
    "feature/python-migration",
    "main",
    "Migrate Python to new architecture",
    "tests/test_mcp_adapter.py: passed"
)
assert "Modernize: Python migration" in pr_template
assert "feature/python-migration" in pr_template
assert "Migrate Python to new architecture" in pr_template
print(f"   ✓ PR template generation")
checklist = ReviewChecklist()
checklist.tests_passing = True
checklist.documentation_updated = True
checklist.security_reviewed = True
checklist.performance_verified = True
ready = checklist.is_ready()
assert ready, "Review checklist should be ready when all checks pass"
print(f"   ✓ Review checklist validation: is_ready={ready}")

# 4. Test ConflictAnalyzer
print("\n4. Testing ConflictAnalyzer")
ca = ConflictAnalyzer()
analysis = ca.analyze_branch_conflict("feature/new-feature", "main")
assert analysis.severity == "low", f"Expected severity low, got {analysis.severity}"
assert analysis.recommended_action == "merge"
assert not ca.should_stop_automated_merge(analysis)
print(f"   ✓ Conflict analysis: severity={analysis.severity}, action={analysis.recommended_action}")

# Test high severity blocking
analysis_high = ConflictAnalysis(
    source_branch="feature/high",
    target_branch="main",
    conflicts=[],
    severity="high",
    requires_immediate_attention=True,
    recommended_action="review",
    estimated_resolution_time="30 minutes",
    risk_assessment="high",
    automation_safe=False,
    manual_review_needed=True,
    recommendations=["Manual review required"],
    timestamp="2026-11-14T19:03:21.224030"
)
assert ca.should_stop_automated_merge(analysis_high), "Should stop merge on high severity"
print(f"   ✓ High severity merge blocking works")

# 5. Test ProjectVersioner
print("\n5. Testing ProjectVersioner")
pv = ProjectVersioner()
version = SemanticVersion(1, 2, 3)
assert str(version) == "1.2.3", f"Unexpected version string: {version}"
print(f"   ✓ Semantic version: {version}")

bump = pv.calculate_version_bump([{"type": "feature"}])
assert bump == VersionBump.MINOR, f"Expected MINOR for feature, got {bump}"
print(f"   ✓ Version bump for feature: {bump}")

next_v = pv.next_version("1.0.0", VersionBump.MAJOR)
assert next_v == "2.0.0", f"Expected 2.0.0 for MAJOR bump, got {next_v}"
next_v = pv.next_version("1.0.0", VersionBump.MINOR)
assert next_v == "1.1.0", f"Expected 1.1.0 for MINOR bump, got {next_v}"
next_v = pv.next_version("1.0.0", VersionBump.PATCH)
assert next_v == "1.0.1", f"Expected 1.0.1 for PATCH bump, got {next_v}"
print(f"   ✓ Version bump calculations: MAJOR->2.0.0, MINOR->1.1.0, PATCH->1.0.1")

# 6. Test RestorationManager
print("\n6. Testing RestorationManager")
rm = RestorationManager()
rm.create_restoration_point("pre-migration", "abc123def456789", "Before migration")
rm.restore_to_point("pre-migration")
print("   ✓ Restoration point creation and restore")

# 7. Test PullRequest dataclass
print("\n7. Testing PullRequest dataclass")
from core.git_intelligence.pull_request_manager import PullRequest
pr = PullRequest(
    title="Test PR",
    source_branch="feature/test",
    target_branch="main",
    description="Test description",
    test_results="tests/test.py: passed",
)
assert pr.title == "Test PR"
assert pr.source_branch == "feature/test"
assert pr.target_branch == "main"
assert pr.test_results == "tests/test.py: passed"
print("   ✓ PullRequest dataclass creation")

print("\n=== ALL GIT INTELLIGENCE TESTS PASSED ===")
print("Git Intelligence subsystem is working correctly!")
