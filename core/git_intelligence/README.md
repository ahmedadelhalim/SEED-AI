# Git Intelligence Subsystem

## Overview

Git Intelligence is SEED's autonomous repository management and project versioning subsystem. It integrates Git operations with central cognition systems to enable:

- **Autonomous feature branch creation** and lifecycle management
- **Intelligent commit tracking** with standardized metadata
- **Pull request creation** with test evidence
- **Conflict analysis** and intelligent resolution recommendations
- **Semantic versioning** for project releases
- **State restoration** from any point in git history

## Core Components

### Branch Manager

Manages git branches including autonomous creation of feature branches.

**Key Features:**
- Auto-generates branch names: `modernize/{language}-{timestamp}`
- Creates autonomous feature branches from any source
- Detects uncommitted changes in workspace
- Integrates with cognition for branch creation decisions

**Usage:**
```python
from core.git_intelligence import BranchManager

bm = BranchManager()

# Auto-generate branch name
branch_name = bm.get_branch_name("python", "2026-11-14T10-00-00Z")
# Returns: "modernize/python-2026-11-14T10-00-00Z"

# Create feature branch
bm.create_feature_branch("feature/new-feature", "main")
```

### Commit Intelligence

Handles git commit operations with standardized metadata and change tracking.

**Key Features:**
- Standardized commit message formatting
- Metadata extraction from commit messages
- Commit format validation (SEED conventions)
- Ticket reference integration (REQ-123)

**Usage:**
```python
from core.git_intelligence import CommitIntelligence

ci = CommitIntelligence()

# Format standardized commit message
ci.format_commit_message("Add new function", "REQ-123", "modernize/python-2026-11-14T10-00-00Z")
# Returns: "Add new function (from modernize/python-2026-11-14T10-00-00Z) [ticket REQ-123]"

# Extract metadata
ci.extract_git_metadata("Add new function (from branch) [ticket REQ-123]")
```

### Pull Request Manager

Manages pull request operations, review checklists, and merge conflict detection.

**Key Features:**
- Standardized PR template generation
- Automated conflict analysis before merge
- Test evidence integration
- Review checklist management

**Usage:**
```python
from core.git_intelligence import PullRequestManager

pm = PullRequestManager()

# Create PR template
pr = pm.create_pr_template(
    title="Modernize: Python migration",
    source_branch="feature/python-migration",
    target_branch="main",
    description="Migrate Python code to new architecture",
    test_results="tests/test_mcp_adapter.py: passed"
)

# Analyze conflicts
conflicts = pm.analyze_conflicts("feature/new-feature", "main")
```

### Conflict Analyzer

Intelligent conflict detection and resolution analysis.

**Key Features:**
- Automated merge conflict analysis
- Severity assessment (low, medium, high)
- Recommended actions (merge, review, resolve)
- Risk assessment and safety checks

**Usage:**
```python
from core.git_intelligence import ConflictAnalyzer

ca = ConflictAnalyzer()
analysis = ca.analyze_branch_conflict("feature/new-feature", "main")

# Check if merge should be blocked
if ca.should_stop_automated_merge(analysis):
    # Block or review merge
    pass
```

### Project Versioner

Semantic versioning for project changes and releases.

**Key Features:**
- Semantic version structure (MAJOR.MINOR.PATCH)
- Automatic version bump detection
- Change type classification (breaking, feature, patch)
- Integration with commit metadata

**Usage:**
```python
from core.git_intelligence import ProjectVersioner, VersionBump

pv = ProjectVersioner()

# Calculate version from changes
changes = [{"type": "feature"}, {"type": "fix"}]
bump = pv.calculate_version_bump(changes)
# Returns: "feature"

# Calculate next version
current = "1.0.0"
next_version = pv.next_version(current, VersionBump.FEATURE)
# Returns: "1.1.0"
```

### Restoration Manager

State restoration from any prior point in git history.

**Key Features:**
- Named restoration points at specific commits
- Soft/hard restoration options
- Integration with cognition state tracking
- Audit trail for restoration operations

**Usage:**
```python
from core.git_intelligence import RestorationManager

rm = RestorationManager()

# Create restoration point
rm.create_restoration_point("pre-migration", "abc123def456789", "Before Python modernization")

# Restore to a specific point
rm.restore_to_point("pre-migration", hard=False)
```

## Integration Points

### With SEED Cognition Systems

Git Intelligence integrates with:

- **Orchestrator**: For autonomous branch management
- **Cognition**: For intelligent feature branch creation
- **Memory**: For storing restoration points and version history
- **Planning**: For version bump planning and release coordination
- **Intelligence**: For intelligent PR analysis and conflict detection

### Integration Examples

**1. Autonomous Branch Creation with Cognition**
```python
from core.git_intelligence import BranchManager
from cognition import Cognition

cognition = Cognition()
branch_manager = BranchManager()

# Cognition decides branch creation based on work queue
if cognition.should_create_feature_branch("python", "migration"):
    branch_manager.create_feature_branch("main", "modernize")
```

**2. Conflict-Analysis with Restoration**
```python
from core.git_intelligence import ConflictAnalyzer, RestorationManager

conflict_analyzer = ConflictAnalyzer()
restoration_manager = RestorationManager()

# Analyze conflicts before merge
analysis = conflict_analyzer.analyze_branch_conflict("feature", "main")
if conflict_analyzer.should_stop_automated_merge(analysis):
    # Restore to safe state
    restoration_manager.restore_to_point("pre-merge", hard=False)
```

**3. Versioning with Planning**
```python
from core.git_intelligence import ProjectVersioner
from planning import Planning

versioner = ProjectVersioner()
planning = Planning()

# Plan version bump based on changes
changes = await planning.analyze_changes()
bump_type = versioner.calculate_version_bump(changes)

# Create release plan
planning.create_release_plan(versioner.next_version("1.0.0", bump_type))
```

## Security Features

Git Intelligence includes security-hardened operations:

1. **Change Validation**: Validates all Git operations before execution
2. **Approval Required**: Non-destructive operations require explicit approval
3. **Audit Trail**: Full audit logging of all Git operations
4. **Restoration Safety**: Restoration points for rollback capabilities
5. **Path Isolation**: All Git operations within workspace boundaries

## Configuration

### Git Intelligence Settings

```python
# Non-destructive operations (always require approval)
git_intelligence_config = {
    "auto_approve_feature_branches": False,
    "require_test_evidence_for_pr": True,
    "block_on_high_conflicts": True,
    "require_approval_for_restore": True,
    "require_ticket_reference": True,
}
```

## Testing and Validation

Git Intelligence includes comprehensive testing:

1. **Branch Management Tests**: Feature branch creation, conflict detection
2. **Commit Intelligence Tests**: Metadata extraction, validation
3. **PR Integration Tests**: Template generation, conflict analysis
4. **Restoration Tests**: Point creation, state restoration

See `tests/` directory for full test suite.

## Future Enhancements

Planned enhancements for future releases:

1. **Advanced Conflict Resolution**: AI-powered conflict resolution
2. **Multi-Repository Coordination**: Cross-repository PR coordination
3. **Automated Testing**: Integrated test generation for feature branches
4. **Release Automation**: Automated release processes with versioning
5. **Performance Monitoring**: Performance metrics for Git operations

## Conclusion

Git Intelligence provides SEED with autonomous repository management capabilities that integrate seamlessly with existing cognition and planning systems. It enables safe, audit-able Git operations with intelligent automation while maintaining strict security controls.

The subsystem supports SEED's autonomous development workflow by enabling intelligent branch creation, conflict analysis, and state restoration, while maintaining full auditability and approval requirements for all operations.