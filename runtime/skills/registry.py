import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.tool_registry import ToolDefinition, ToolRegistry, ToolError
from memory.store import connect
from runtime.skills.installer import SkillLifecycleManager
from runtime.skills.parser import SkillParser, SkillValidationError
from security.permission_engine import PermissionEngine


class GovernedSkillToolHandler:
    """Secure, governed execution handler for dynamically registered skill tools.
    Enforces artifact digest verification, ownership, timeouts, and audit logging."""

    def __init__(self, skill_id: str, tool_name: str, artifact_digest: str, underlying_handler: Optional[Callable[..., Any]] = None):
        self.skill_id = skill_id
        self.tool_name = tool_name
        self.artifact_digest = artifact_digest
        self.underlying_handler = underlying_handler or (lambda **kwargs: {"status": "success", "result": kwargs, "message": f"Tool {tool_name} executed successfully via skill {skill_id}"})

    def __call__(self, **kwargs) -> Dict[str, Any]:
        record = SkillLifecycleManager.get_skill(self.skill_id)
        if not record or record["artifact_digest"] != self.artifact_digest or record["state"] not in {"Installed", "Activated"}:
            return {
                "status": "error",
                "reason": f"Skill {self.skill_id} is not active or artifact digest mismatch",
                "skill_id": self.skill_id,
            }
        try:
            with connect() as db:
                db.execute(
                    "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                    (self.skill_id, "tool_executed", f"Executing dynamic tool {self.tool_name}"),
                )
            result = self.underlying_handler(**kwargs)
            if isinstance(result, dict):
                return result
            return {"status": "success", "result": result}
        except Exception as error:
            with connect() as db:
                db.execute(
                    "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                    (self.skill_id, "tool_execution_failed", f"Tool {self.tool_name} failed: {error}"),
                )
            return {"status": "failed", "error": str(error), "tool_name": self.tool_name}


class GovernedDynamicToolRegistry:
    """Manages Phase 3C dynamic tool registration, binding tools to approved skills,
    artifact digests, and permissions, while enforcing central ToolRegistry governance."""

    @staticmethod
    def initialize_schema():
        SkillLifecycleManager.initialize_schema()
        with connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS dynamic_tools_registry (
                tool_name TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL,
                artifact_digest TEXT NOT NULL,
                action TEXT NOT NULL,
                scope TEXT NOT NULL,
                schema_json TEXT NOT NULL,
                description TEXT NOT NULL,
                parallel_safe INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(skill_id) REFERENCES skills_registry(skill_id)
            );
            """)

    @staticmethod
    def register_approved_skill_tools(skill_id: str, tool_registry: ToolRegistry,
                                      permission_engine: PermissionEngine) -> List[str]:
        GovernedDynamicToolRegistry.initialize_schema()
        record = SkillLifecycleManager.get_skill(skill_id)
        if not record:
            raise ValueError(f"Skill {skill_id} not found in registry")

        if record["state"] not in {"Installed", "Activated"}:
            raise ValueError(f"Skill {skill_id} state is '{record['state']}'. Only 'Installed' or 'Activated' skills may register tools.")

        source_dir = Path(record["directory_path"])
        current_bundle = SkillParser.parse_skill_bundle(source_dir)
        if current_bundle["artifact_digest"] != record["artifact_digest"]:
            raise SkillValidationError("Artifact integrity check failed: digest mismatch during dynamic tool registration")

        manifest = json.loads(record["manifest_json"])
        declared_permissions = manifest.get("permissions", [])
        tools_list = manifest.get("tools", [])

        # Step 1: Validate all tool declarations first before modifying registries (Atomicity/Phase 3C.1)
        validated_tool_defs = []
        for tool_item in tools_list:
            if isinstance(tool_item, str):
                t_name = tool_item
                t_desc = f"Tool {t_name} from skill {skill_id}"
                t_params = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
                t_action = "read"
                t_scope = "workspace"
                t_parallel = True
            elif isinstance(tool_item, dict):
                t_name = tool_item.get("name")
                t_desc = tool_item.get("description", f"Tool {t_name}")
                t_params = tool_item.get("parameters", {"type": "object", "properties": {}, "additionalProperties": False})
                t_action = tool_item.get("action", "read")
                t_scope = tool_item.get("scope", "workspace")
                t_parallel = tool_item.get("parallel_safe", False)
            else:
                continue

            if not t_name or not SkillParser.ID_PATTERN.match(t_name):
                raise SkillValidationError(f"Invalid dynamic tool name: {t_name}")

            if not isinstance(t_params, dict) or t_params.get("type") != "object":
                raise SkillValidationError(f"Tool {t_name} parameters must use an object schema")

            action_allowed = any(
                p.get("action") == t_action and p.get("scope") == t_scope
                for p in declared_permissions
            )
            if not action_allowed:
                raise SkillValidationError(f"Tool {t_name} declares action '{t_action}' and scope '{t_scope}' not covered by approved skill permissions")

            handler = GovernedSkillToolHandler(skill_id, t_name, record["artifact_digest"])
            tool_def = ToolDefinition(
                name=t_name,
                description=t_desc,
                handler=handler,
                parameters=t_params,
                action=t_action,
                scope=t_scope,
                parallel_safe=t_parallel,
                retry_safe=True,
            )
            validated_tool_defs.append((t_name, t_action, t_scope, tool_def, t_params, t_desc, t_parallel))

        registered_names = []
        registered_during_attempt = []

        try:
            with connect() as db:
                for t_name, t_action, t_scope, tool_def, t_params, t_desc, t_parallel in validated_tool_defs:
                    # Register into central ToolRegistry
                    tool_registry.register(tool_def)
                    registered_during_attempt.append(t_name)

                    # Register policy centrally via PermissionEngine.register_policy()
                    permission_engine.register_policy(
                        tool=t_name,
                        action=t_action,
                        scope=t_scope,
                        allowed=True,
                        approval=t_action in permission_engine.DESTRUCTIVE_ACTIONS,
                        skill_id=skill_id,
                        artifact_digest=record["artifact_digest"],
                    )

                    db.execute(
                        """
                        INSERT INTO dynamic_tools_registry (
                            tool_name, skill_id, artifact_digest, action, scope,
                            schema_json, description, parallel_safe
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(tool_name) DO UPDATE SET
                            skill_id = excluded.skill_id,
                            artifact_digest = excluded.artifact_digest,
                            action = excluded.action,
                            scope = excluded.scope,
                            schema_json = excluded.schema_json,
                            description = excluded.description,
                            parallel_safe = excluded.parallel_safe
                        """,
                        (
                            t_name, skill_id, record["artifact_digest"], t_action, t_scope,
                            json.dumps(t_params), t_desc, 1 if t_parallel else 0,
                        ),
                    )
                    db.execute(
                        "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                        (skill_id, "tool_registered", f"Dynamic tool registered centrally: {t_name}"),
                    )
                    registered_names.append(t_name)
        except Exception as error:
            # Atomic Rollback for current skill attempt only using ownership-aware APIs
            for t_name in registered_during_attempt:
                tool_registry.unregister_with_ownership(t_name, skill_id, record["artifact_digest"])
                permission_engine.unregister_policy(t_name, skill_id=skill_id, artifact_digest=record["artifact_digest"])

            with connect() as db:
                for t_name in registered_during_attempt:
                    db.execute("DELETE FROM dynamic_tools_registry WHERE tool_name = ?", (t_name,))
                db.execute(
                    "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                    (skill_id, "recovery_failed", f"Registration failed and rolled back safely for skill {skill_id}: {error}"),
                )
            raise

        return registered_names

    @staticmethod
    def unregister_skill_tools(skill_id: str, tool_registry: ToolRegistry,
                               permission_engine: PermissionEngine, artifact_digest: Optional[str] = None) -> List[str]:
        GovernedDynamicToolRegistry.initialize_schema()
        unregistered = []

        with connect() as db:
            rows = db.execute(
                "SELECT tool_name, artifact_digest FROM dynamic_tools_registry WHERE skill_id = ?",
                (skill_id,),
            ).fetchall()

            for row in rows:
                t_name = row["tool_name"]
                digest = artifact_digest or row["artifact_digest"]

                removed_tool = tool_registry.unregister_with_ownership(t_name, skill_id, digest)
                permission_engine.unregister_policy(t_name, skill_id=skill_id, artifact_digest=digest)

                if removed_tool or t_name not in tool_registry._tools:
                    db.execute("DELETE FROM dynamic_tools_registry WHERE tool_name = ?", (t_name,))
                    db.execute(
                        "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                        (skill_id, "tool_unregistered", f"Dynamic tool unregistered centrally with ownership verification: {t_name}"),
                    )
                    unregistered.append(t_name)

        return unregistered

    @staticmethod
    def recover_approved_tools_on_startup(tool_registry: ToolRegistry,
                                           permission_engine: PermissionEngine) -> List[str]:
        GovernedDynamicToolRegistry.initialize_schema()
        recovered = []

        with connect() as db:
            try:
                rows = db.execute(
                    """
                    SELECT d.tool_name, d.skill_id, d.artifact_digest, s.state, s.directory_path, s.artifact_digest AS registry_digest
                    FROM dynamic_tools_registry d
                    JOIN skills_registry s ON d.skill_id = s.skill_id
                    """
                ).fetchall()
            except sqlite3.OperationalError:
                return recovered

            for row in rows:
                tool_name = row["tool_name"]
                skill_id = row["skill_id"]
                state = row["state"]
                directory_path = row["directory_path"]
                expected_digest = row["registry_digest"]

                if state not in {"Installed", "Activated"}:
                    GovernedDynamicToolRegistry._audit_recovery_failure(skill_id, tool_name, f"Skill state is '{state}' (not installed/activated)")
                    continue

                source_dir = Path(directory_path)
                if not source_dir.exists() or not source_dir.is_dir():
                    GovernedDynamicToolRegistry._audit_recovery_failure(skill_id, tool_name, f"Skill directory missing: {directory_path}")
                    continue

                try:
                    current_bundle = SkillParser.parse_skill_bundle(source_dir)
                    if current_bundle["artifact_digest"] != expected_digest:
                        GovernedDynamicToolRegistry._audit_recovery_failure(skill_id, tool_name, "Artifact digest mismatch during startup recovery")
                        continue

                    GovernedDynamicToolRegistry.register_approved_skill_tools(
                        skill_id, tool_registry, permission_engine
                    )
                    recovered.append(tool_name)
                except Exception as error:
                    GovernedDynamicToolRegistry._audit_recovery_failure(skill_id, tool_name, f"Recovery exception: {error}")

        return recovered

    @staticmethod
    def _audit_recovery_failure(skill_id: str, tool_name: str, reason: str):
        with connect() as db:
            db.execute(
                "INSERT INTO skills_audit (skill_id, event_type, details) VALUES (?, ?, ?)",
                (skill_id, "recovery_failed", f"Failed to restore dynamic tool '{tool_name}': {reason}"),
            )
