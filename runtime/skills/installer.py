import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from memory.store import connect
from runtime.skills.parser import SkillParser, SkillValidationError


class SkillLifecycleManager:
    """Manages Phase 3A skill discovery, validation, and lifecycle states."""

    VALID_STATES = {
        "Discovered", "Parsed", "Validated", "ProvenanceChecked",
        "ReviewRequested", "AdminApproved", "AdminRejected",
        "Installed", "Registered", "Activated", "Disabled",
        "Revoked", "Uninstalled", "RolledBack"
    }

    @staticmethod
    def initialize_schema():
        # Skill and approval persistence share the application's schema.
        from memory import store
        store.initialize()
        with connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS skills_registry (
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                artifact_digest TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'Discovered',
                manifest_json TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                reviewer_id TEXT,
                approved_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS skills_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(skill_id) REFERENCES skills_registry(skill_id)
            );
            """)

    @staticmethod
    def discover_skills(skills_root: Path) -> List[Dict[str, Any]]:
        SkillLifecycleManager.initialize_schema()
        skills_root = skills_root.resolve()
        discovered = []

        if not skills_root.exists() or not skills_root.is_dir():
            return discovered

        seen_names = set()

        for child in sorted(skills_root.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                try:
                    bundle = SkillParser.parse_skill_bundle(child)
                    name = bundle["manifest"]["name"]
                    version = bundle["manifest"]["version"]

                    if name in seen_names:
                        raise SkillValidationError(f"Duplicate skill identifier detected during discovery: {name}")
                    seen_names.add(name)

                    skill_id = f"{name}@{version}"
                    bundle["skill_id"] = skill_id
                    bundle["state"] = "Validated"
                    discovered.append(bundle)

                    # Persist discovery state
                    SkillLifecycleManager._upsert_skill_record(
                        skill_id=skill_id,
                        name=name,
                        version=version,
                        artifact_digest=bundle["artifact_digest"],
                        state="Validated",
                        manifest_json=json.dumps(bundle["manifest"]),
                        directory_path=str(child),
                    )
                except Exception as error:
                    # Log or record validation failure safely without crashing discovery
                    continue

        return discovered

    @staticmethod
    def _upsert_skill_record(skill_id: str, name: str, version: str,
                             artifact_digest: str, state: str,
                             manifest_json: str, directory_path: str,
                             reviewer_id: Optional[str] = None,
                             approved_at: Optional[str] = None):
        with connect() as db:
            db.execute(
                """
                INSERT INTO skills_registry (
                    skill_id, name, version, artifact_digest, state,
                    manifest_json, directory_path, reviewer_id, approved_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(skill_id) DO UPDATE SET
                    artifact_digest = excluded.artifact_digest,
                    state = excluded.state,
                    manifest_json = excluded.manifest_json,
                    directory_path = excluded.directory_path,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    skill_id, name, version, artifact_digest, state,
                    manifest_json, directory_path, reviewer_id, approved_at,
                ),
            )
            db.execute(
                "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                (skill_id, f"state_{state.lower()}", f"Skill recorded in state {state}"),
            )

    @staticmethod
    def get_skill(skill_id: str) -> Optional[Dict[str, Any]]:
        with connect() as db:
            row = db.execute(
                "SELECT * FROM skills_registry WHERE skill_id = ?",
                (skill_id,),
            ).fetchone()
            if not row:
                return None
            return dict(row)
