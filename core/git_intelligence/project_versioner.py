"""
Project Versioner - Semantic Versioning for Project Changes
Handles semantic version bumps and release versioning for SEED project.
"""


class SemanticVersion:
    """Semantic version structure for tracking releases."""
    def __init__(self, major: int, minor: int, patch: int):
        self.major = major
        self.minor = minor
        self.patch = patch

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"


class VersionBump:
    """Enum for version bump types."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    FEATURE = "feature"


class ProjectVersioner:
    """Manages semantic versioning of project changes and releases."""

    @staticmethod
    def calculate_version_bump(changes: list) -> VersionBump:
        """
        Determine version bump based on change type.

        Args:
            changes: List of change objects, e.g., [{"type": "breaking"}, {"type": "feature"}]

        Returns:
            VersionBump enum value
        """
        change_types = [c.get("type") for c in changes if isinstance(c, dict)]

        if "breaking" in change_types or "major" in change_types:
            return VersionBump.MAJOR
        elif "feature" in change_types or "minor" in change_types:
            return VersionBump.MINOR
        return VersionBump.PATCH

    @staticmethod
    def next_version(current_version: str, bump: VersionBump) -> str:
        """Calculate next version based on current version and bump type."""
        parts = [int(p) for p in current_version.split(".")]
        while len(parts) < 3:
            parts.append(0)

        major, minor, patch = parts

        # FEATURE is semantically equivalent to MINOR in semver.
        if bump in (VersionBump.MAJOR, VersionBump.MINOR, VersionBump.FEATURE):
            if bump == VersionBump.MAJOR:
                return f"{major + 1}.0.0"
            else:
                return f"{major}.{minor + 1}.0"
        return f"{major}.{minor}.{patch + 1}"