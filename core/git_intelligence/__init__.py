"""
SEED Git Intelligence - Autonomous Repository and Project Versioning
Integrates Git with central cognition systems for SEED autonomous operations
"""

from .branch_manager import BranchManager, FeatureBranch, BranchStrategy
from .commit_intelligence import CommitIntelligence, GitCommit
from .pull_request_manager import PullRequestManager, PullRequest, ReviewChecklist
from .conflict_analyzer import ConflictAnalyzer, ConflictAnalysis
from .project_versioner import ProjectVersioner, SemanticVersion, VersionBump
from .restoration_manager import RestorationManager, RestorationPoint

__all__ = [
    "BranchManager",
    "FeatureBranch",
    "BranchStrategy",
    "CommitIntelligence",
    "GitCommit",
    "PullRequestManager",
    "PullRequest",
    "ReviewChecklist",
    "ConflictAnalyzer",
    "ConflictAnalysis",
    "ProjectVersioner",
    "SemanticVersion",
    "VersionBump",
    "RestorationManager",
    "RestorationPoint",
]

__version__ = "1.0.0"