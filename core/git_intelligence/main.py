"""
Main entry point for Git Intelligence subsystem.
Orchestrates branch management, commit intelligence, PR creation, conflict analysis,
versioning, and restoration.

Usage:
    from core.git_intelligence import (
        BranchManager, CommitIntelligence, PullRequestManager,
        ConflictAnalyzer, ProjectVersioner, RestorationManager
    )

Example:
    bm = BranchManager()
    ci = CommitIntelligence()
    pm = PullRequestManager()
    ca = ConflictAnalyzer()
    pv = ProjectVersioner()
    rm = RestorationManager()

    # Create feature branch
    bm.create_feature_branch("feature/new-feature", "main")

    # Track commits with metadata
    ci.format_commit_message("Add new function")

    # Analyze conflicts before merge
    ca.analyze_branch_conflict("feature/new-feature", "main")

    # Bump version after changes
    pv.next_version("1.0.0", VersionBump.FEATURE)
    
    # Restore to previous state
    rm.create_restoration_point("pre-migration", "abc123def")
"""

from .branch_manager import BranchManager
from .commit_intelligence import CommitIntelligence
from .pull_request_manager import PullRequestManager
from .conflict_analyzer import ConflictAnalyzer
from .project_versioner import ProjectVersioner, VersionBump
from .restoration_manager import RestorationManager

__all__ = [
    "BranchManager",
    "CommitIntelligence",
    "PullRequestManager",
    "ConflictAnalyzer",
    "ProjectVersioner",
    "RestorationManager",
]
