"""
Commit Intelligence - Git Commit Operations with Metadata Tracking
Handles git commit operations with standardized metadata and change tracking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


TICKET_PATTERN = re.compile(r"\[ticket\s+([^\]]+)\]")
BRANCH_PATTERN = re.compile(r"\(from\s+([^)]+)\)")


@dataclass
class GitCommit:
    """Represents a git commit with SEED-standard metadata."""

    message: str
    ticket_ref: Optional[str] = None
    branch: Optional[str] = None
    author: Optional[str] = None
    files_changed: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    commit_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CommitIntelligence:
    """Manages git commit operations with standardized metadata and change tracking."""

    @staticmethod
    def format_commit_message(
        description: str,
        ticket_ref: Optional[str] = None,
        branch_name: Optional[str] = None,
    ) -> str:
        """Format a standardized SEED git commit message.

        Args:
            description: Brief present-tense description of the change.
            ticket_ref: Optional ticket/requirement reference (e.g., 'REQ-123').
            branch_name: Optional originating branch for provenance.

        Returns:
            Formatted commit message string.
        """
        parts = [description.strip()]
        if branch_name:
            parts.append(f"(from {branch_name})")
        if ticket_ref:
            parts.append(f"[ticket {ticket_ref}]")
        return " ".join(parts)

    @staticmethod
    def extract_git_metadata(commit_text: str) -> Dict[str, Optional[str]]:
        """Extract structured metadata from a commit message.

        Args:
            commit_text: Raw commit message text.

        Returns:
            Dict with ``description``, ``ticket_ref`` and ``branch`` keys.
        """
        ticket_match = TICKET_PATTERN.search(commit_text)
        branch_match = BRANCH_PATTERN.search(commit_text)

        description = TICKET_PATTERN.sub("", commit_text)
        description = BRANCH_PATTERN.sub("", description).strip()

        return {
            "description": description or None,
            "ticket_ref": ticket_match.group(1).strip() if ticket_match else None,
            "branch": branch_match.group(1).strip() if branch_match else None,
        }

    @staticmethod
    def validate_commit_format(commit_msg: str) -> bool:
        """Validate that a commit message follows SEED conventions."""
        if not commit_msg or not commit_msg.strip():
            return False
        return bool(
            TICKET_PATTERN.search(commit_msg) or BRANCH_PATTERN.search(commit_msg)
        )

    @staticmethod
    def build_commit(
        description: str,
        ticket_ref: Optional[str] = None,
        branch_name: Optional[str] = None,
    ) -> GitCommit:
        """Build a :class:`GitCommit` with formatted message and metadata."""
        message = CommitIntelligence.format_commit_message(
            description, ticket_ref, branch_name
        )
        return GitCommit(
            message=message,
            ticket_ref=ticket_ref,
            branch=branch_name,
        )