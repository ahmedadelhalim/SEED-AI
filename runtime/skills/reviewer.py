import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from memory.store import connect
from runtime.skills.installer import SkillLifecycleManager
from runtime.skills.parser import SkillParser, SkillValidationError


class AdminSkillReviewer:
    """Handles Phase 3B administrative review, approval, rejection, installation, and activation workflow."""

    STAGING_ROOT = Path(tempfile.gettempdir()) / "seed-skill-staging"

    @staticmethod
    def request_review_approval(skill_id: str, approval_manager, identity) -> Dict[str, Any]:
        if not identity or identity.kind != "admin" or not identity.principal_id:
            raise ValueError("Administrative identity is required for skill review")
        record = SkillLifecycleManager.get_skill(skill_id)
        if not record:
            raise ValueError(f"Skill {skill_id} not found in registry")
        if record["state"] != "Validated":
            raise ValueError(f"Skill cannot request review from state '{record['state']}'")
        with connect() as db:
            db.execute(
                "UPDATE skills_registry SET state = 'ReviewRequested', updated_at = CURRENT_TIMESTAMP WHERE skill_id = ?",
                (skill_id,),
            )
            db.execute(
                "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                (skill_id, "review_requested", f"Review requested by {identity.principal_id}"),
            )
        approval = approval_manager.request(
            tool="skill.review",
            action="modify",
            scope="resource",
            arguments={"skill_id": skill_id},
            identity=identity,
        )
        return {"approval_id": approval.approval_id, "skill_id": skill_id}

    @staticmethod
    def review_and_approve(skill_id: str, approval_id: str, identity,
                           approval_manager, decision: str, rationale: str) -> Dict[str, Any]:
        if not identity or identity.kind != "admin" or not identity.principal_id:
            raise ValueError("Administrative identity is required for skill review")
        if decision not in {"approve", "reject"}:
            raise ValueError("Decision must be either 'approve' or 'reject'")
        if not approval_manager.consume(
            approval_id, "skill.review", "modify", "resource",
            {"skill_id": skill_id}, identity,
        ):
            raise ValueError("Review approval is invalid, expired, or already consumed")
        result = AdminSkillReviewer.review_skill(
            skill_id, identity.principal_id, decision, rationale
        )
        if decision == "approve":
            record = SkillLifecycleManager.get_skill(skill_id)
            staged_path = AdminSkillReviewer.STAGING_ROOT / skill_id.replace("@", "-")
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            if staged_path.exists():
                shutil.rmtree(staged_path)
            shutil.copytree(record["directory_path"], staged_path)
            result["staged_path"] = str(staged_path)
        return result

    @staticmethod
    def review_skill(skill_id: str, reviewer_id: str, decision: str, rationale: str) -> Dict[str, Any]:
        if not reviewer_id or not isinstance(reviewer_id, str):
            raise ValueError("Valid reviewer_id is required for administrative review")

        if decision not in {"approve", "reject"}:
            raise ValueError("Decision must be either 'approve' or 'reject'")

        record = SkillLifecycleManager.get_skill(skill_id)
        if not record:
            raise ValueError(f"Skill {skill_id} not found in registry. Run discovery first.")

        # Verify artifact integrity (re-parse current bundle on disk)
        current_bundle = SkillParser.parse_skill_bundle(Path(record["directory_path"]))
        current_digest = current_bundle["artifact_digest"]

        if current_digest != record["artifact_digest"]:
            # Artifact modified since discovery/validation -> invalidate
            with connect() as db:
                db.execute(
                    "UPDATE skills_registry SET state = 'Revoked', updated_at = CURRENT_TIMESTAMP WHERE skill_id = ?",
                    (skill_id,),
                )
                db.execute(
                    "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                    (skill_id, "artifact_tampered", "Artifact digest mismatch detected during review"),
                )
            raise SkillValidationError("Artifact integrity check failed: skill content was modified after discovery")

        new_state = "AdminApproved" if decision == "approve" else "AdminRejected"
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        with connect() as db:
            db.execute(
                """
                UPDATE skills_registry
                SET state = ?, reviewer_id = ?, approved_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE skill_id = ?
                """,
                (new_state, reviewer_id, now_str if decision == "approve" else None, skill_id),
            )
            db.execute(
                "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                (skill_id, f"review_{decision}d", f"Reviewed by {reviewer_id}: {rationale}"),
            )

        return {
            "status": "success",
            "skill_id": skill_id,
            "state": new_state,
            "reviewer_id": reviewer_id,
        }

    @staticmethod
    def install_skill(skill_id: str, operator_id: str) -> Dict[str, Any]:
        record = SkillLifecycleManager.get_skill(skill_id)
        if not record:
            raise ValueError(f"Skill {skill_id} not found")

        if record["state"] != "AdminApproved":
            raise ValueError(f"Skill cannot be installed from state '{record['state']}'. Must be 'AdminApproved'.")

        with connect() as db:
            db.execute(
                "UPDATE skills_registry SET state = 'Installed', updated_at = CURRENT_TIMESTAMP WHERE skill_id = ?",
                (skill_id,),
            )
            db.execute(
                "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                (skill_id, "state_installed", f"Installed by {operator_id}"),
            )

        return {"status": "success", "skill_id": skill_id, "state": "Installed"}

    @staticmethod
    def activate_skill(skill_id: str, operator_id: str) -> Dict[str, Any]:
        record = SkillLifecycleManager.get_skill(skill_id)
        if not record:
            raise ValueError(f"Skill {skill_id} not found")

        if record["state"] != "Installed":
            raise ValueError(f"Skill cannot be activated from state '{record['state']}'. Must be 'Installed'.")

        # Verify artifact integrity once more before activation
        current_bundle = SkillParser.parse_skill_bundle(Path(record["directory_path"]))
        if current_bundle["artifact_digest"] != record["artifact_digest"]:
            raise SkillValidationError("Artifact integrity check failed prior to activation: digest mismatch")

        with connect() as db:
            db.execute(
                "UPDATE skills_registry SET state = 'Activated', updated_at = CURRENT_TIMESTAMP WHERE skill_id = ?",
                (skill_id,),
            )
            db.execute(
                "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                (skill_id, "state_activated", f"Activated by {operator_id}"),
            )

        return {"status": "success", "skill_id": skill_id, "state": "Activated"}

    @staticmethod
    def deactivate_skill(skill_id: str, operator_id: str) -> Dict[str, Any]:
        record = SkillLifecycleManager.get_skill(skill_id)
        if not record:
            raise ValueError(f"Skill {skill_id} not found")

        if record["state"] != "Activated":
            raise ValueError(f"Skill cannot be deactivated from state '{record['state']}'. Must be 'Activated'.")

        with connect() as db:
            db.execute(
                "UPDATE skills_registry SET state = 'Disabled', updated_at = CURRENT_TIMESTAMP WHERE skill_id = ?",
                (skill_id,),
            )
            db.execute(
                "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                (skill_id, "state_disabled", f"Disabled by {operator_id}"),
            )

        return {"status": "success", "skill_id": skill_id, "state": "Disabled"}

    @staticmethod
    def uninstall_skill(skill_id: str, operator_id: str) -> Dict[str, Any]:
        record = SkillLifecycleManager.get_skill(skill_id)
        if not record:
            raise ValueError(f"Skill {skill_id} not found")

        with connect() as db:
            db.execute(
                "UPDATE skills_registry SET state = 'Uninstalled', updated_at = CURRENT_TIMESTAMP WHERE skill_id = ?",
                (skill_id,),
            )
            db.execute(
                "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                (skill_id, "state_uninstalled", f"Uninstalled by {operator_id}"),
            )

        return {"status": "success", "skill_id": skill_id, "state": "Uninstalled"}

    @staticmethod
    def search_skills(query: str = "") -> List[Dict[str, Any]]:
        with connect() as db:
            pattern = f"%{query.lower()}%"
            rows = db.execute(
                "SELECT * FROM skills_registry WHERE LOWER(skill_id) LIKE ? OR LOWER(name) LIKE ? OR LOWER(manifest_json) LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            return [dict(row) for row in rows]
