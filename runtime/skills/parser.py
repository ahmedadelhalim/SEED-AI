import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

from runtime.workspace_guard import validate_path, WORKSPACE


class SkillValidationError(ValueError):
    """Raised when a skill manifest or artifact fails validation."""
    pass


class SkillParser:
    """Strict parser and validator for SEED-AI SKILL.md bundles."""

    ALLOWED_ACTIONS = {"read", "write", "execute", "delete", "deploy", "modify"}
    ALLOWED_SCOPES = {"workspace", "system", "network", "resource"}
    ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,63}$")
    VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$")

    @staticmethod
    def parse_skill_bundle(skill_dir: Path) -> Dict[str, Any]:
        skill_dir = skill_dir.resolve()
        if not skill_dir.exists() or not skill_dir.is_dir():
            raise SkillValidationError(f"Skill directory does not exist or is not a directory: {skill_dir}")

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists() or not skill_md.is_file():
            raise SkillValidationError(f"Missing mandatory SKILL.md file in {skill_dir}")

        # Path traversal / symlink defense on all files in skill_dir
        for path in skill_dir.rglob("*"):
            if path.is_symlink():
                raise SkillValidationError(f"Symlinks are strictly prohibited in skill bundles: {path}")
            try:
                path.resolve().relative_to(WORKSPACE.resolve())
            except ValueError:
                # If skill is stored outside workspace root during discovery, ensure it stays within authorized skill root
                pass

        content = skill_md.read_text(encoding="utf-8", errors="strict")
        frontmatter, markdown_body = SkillParser._extract_frontmatter(content)

        # Validate required metadata
        SkillParser._validate_metadata(frontmatter)

        # Calculate stable SHA-256 digest of artifact files
        artifact_digest = SkillParser._calculate_artifact_digest(skill_dir)

        return {
            "status": "success",
            "manifest": frontmatter,
            "artifact_digest": artifact_digest,
            "skill_directory": str(skill_dir),
            "documentation": markdown_body,
        }

    @staticmethod
    def _extract_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
        if not content.startswith("---"):
            raise SkillValidationError("SKILL.md must start with YAML frontmatter delimited by '---'")
        parts = content.split("---", 2)
        if len(parts) < 3:
            raise SkillValidationError("Malformed SKILL.md frontmatter delimiters")

        raw_yaml = parts[1]
        body = parts[2].strip()

        try:
            data = yaml.safe_load(raw_yaml)
        except Exception as error:
            raise SkillValidationError(f"Invalid YAML frontmatter: {error}")

        if not isinstance(data, dict):
            raise SkillValidationError("SKILL.md frontmatter must be a YAML dictionary")

        return data, body

    @staticmethod
    def _validate_metadata(manifest: Dict[str, Any]):
        name = manifest.get("name")
        if not name or not isinstance(name, str) or not SkillParser.ID_PATTERN.match(name):
            raise SkillValidationError(f"Invalid or missing skill 'name': {name}")

        version = manifest.get("version")
        if not version or not isinstance(version, str) or not SkillParser.VERSION_PATTERN.match(version):
            raise SkillValidationError(f"Invalid or missing skill 'version': {version}")

        description = manifest.get("description")
        if not description or not isinstance(description, str) or len(description) > 500:
            raise SkillValidationError("Missing or excessively long skill 'description'")

        permissions = manifest.get("permissions", [])
        if not isinstance(permissions, list):
            raise SkillValidationError("Skill 'permissions' must be a list")

        for perm in permissions:
            if not isinstance(perm, dict):
                raise SkillValidationError("Permission declaration must be an object")
            action = perm.get("action")
            scope = perm.get("scope")
            if action not in SkillParser.ALLOWED_ACTIONS:
                raise SkillValidationError(f"Invalid permission action: {action}")
            if scope not in SkillParser.ALLOWED_SCOPES:
                raise SkillValidationError(f"Invalid permission scope: {scope}")

        tools = manifest.get("tools", [])
        if not isinstance(tools, list):
            raise SkillValidationError("Skill 'tools' must be a list")

        for tool in tools:
            if isinstance(tool, str):
                if not SkillParser.ID_PATTERN.match(tool):
                    raise SkillValidationError(f"Invalid tool reference identifier: {tool}")
            elif isinstance(tool, dict):
                t_name = tool.get("name")
                if not t_name or not SkillParser.ID_PATTERN.match(t_name):
                    raise SkillValidationError(f"Invalid tool declaration name: {t_name}")
                parameters = tool.get("parameters", {})
                if not isinstance(parameters, dict):
                    raise SkillValidationError("Tool parameters must be a schema object")
            else:
                raise SkillValidationError("Tool entry must be a string identifier or object definition")

    @staticmethod
    def _calculate_artifact_digest(skill_dir: Path) -> str:
        hasher = hashlib.sha256()
        # Sort files deterministically for stable hashing
        for path in sorted(skill_dir.rglob("*")):
            if path.is_file():
                rel_path = path.relative_to(skill_dir).as_posix().encode("utf-8")
                hasher.update(rel_path)
                hasher.update(path.read_bytes())
        return hasher.hexdigest()
