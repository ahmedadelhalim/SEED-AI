
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DecisionOutcome(Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass(frozen=True)
class ExecutionIdentity:
    principal_id: str = "local"
    kind: str = "user"
    project_id: Optional[str] = None
    workspace_id: Optional[str] = None
    environment: Optional[str] = None


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    requires_approval: bool
    reason: str
    outcome: DecisionOutcome = DecisionOutcome.DENY


class PermissionEngine:

    DESTRUCTIVE_ACTIONS = {"write", "delete", "execute", "deploy", "modify"}

    TOOL_POLICIES = {
        "workspace.list": {
            "action": "read",
            "scope": "workspace",
            "allowed": True,
            "approval": False,
        },
        "system.health": {
            "action": "read",
            "scope": "system",
            "allowed": True,
            "approval": False,
        },
        "file.read": {
            "action": "read",
            "scope": "workspace",
            "allowed": True,
            "approval": False,
        },
        "file.search": {
            "action": "read",
            "scope": "workspace",
            "allowed": True,
            "approval": False,
        },
        "file.write": {
            "action": "write",
            "scope": "workspace",
            "allowed": True,
            "approval": True,
        },
        "system.windows_host": {
            "action": "read",
            "scope": "system",
            "allowed": True,
            "approval": False,
        },
        "system.windows_cpu_memory": {
            "action": "read",
            "scope": "system",
            "allowed": True,
            "approval": False,
        },
        "system.windows_disk_volumes": {
            "action": "read",
            "scope": "system",
            "allowed": True,
            "approval": False,
        },
        "system.windows_processes": {
            "action": "read",
            "scope": "system",
            "allowed": True,
            "approval": False,
        },
        "system.windows_network": {
            "action": "read",
            "scope": "system",
            "allowed": True,
            "approval": False,
        },
    }

    def unregister_policy(self, tool: str, skill_id: Optional[str] = None, artifact_digest: Optional[str] = None):
        policy = self.TOOL_POLICIES.get(tool)
        if not policy or tool in self.PROTECTED_STATIC_POLICIES:
            return False
        # Dynamic policies are ownership-bound.  Omitting either binding must
        # never permit removal of a policy registered by another skill.
        if (
            not skill_id
            or not artifact_digest
            or policy.get("skill_id") != skill_id
            or policy.get("artifact_digest") != artifact_digest
        ):
            return False
        del self.TOOL_POLICIES[tool]
        return True

    PROTECTED_STATIC_POLICIES = {
        "workspace.list", "system.health", "file.read", "file.search", "file.write",
        "system.windows_host", "system.windows_cpu_memory", "system.windows_disk_volumes",
        "system.windows_processes", "system.windows_network",
    }

    def register_policy(self, tool: str, action: str, scope: str,
                        allowed: bool = True, approval: bool = False,
                        skill_id: Optional[str] = None,
                        artifact_digest: Optional[str] = None):
        if not tool or not isinstance(tool, str):
            raise ValueError("Tool name is required for policy registration")
        if tool in self.PROTECTED_STATIC_POLICIES:
            raise PermissionError(f"Cannot overwrite protected static policy for tool: {tool}")
        if action not in {"read", "write", "execute", "delete", "deploy", "modify"}:
            raise ValueError(f"Invalid permission action: {action}")
        if scope not in {"workspace", "system", "network", "resource"}:
            raise ValueError(f"Invalid permission scope: {scope}")

        self.TOOL_POLICIES[tool] = {
            "action": action,
            "scope": scope,
            "allowed": allowed,
            "approval": approval,
            "skill_id": skill_id,
            "artifact_digest": artifact_digest,
        }

    def check(self, action: str, tool: str = "", scope: str = "",
              identity: Optional[ExecutionIdentity] = None,
              resource: Optional[str] = None,
              operation: Optional[str] = None,
              environment: Optional[str] = None):
        policy = self.TOOL_POLICIES.get(tool)

        if policy is None:
            return PermissionDecision(
                False, False, "Unknown tool denied by default", DecisionOutcome.DENY
            )

        if action != policy["action"]:
            return PermissionDecision(
                False, False, "Action does not match tool policy", DecisionOutcome.DENY
            )

        if scope != policy["scope"]:
            return PermissionDecision(
                False, False, "Requested scope is not authorized", DecisionOutcome.DENY
            )

        identity = identity or ExecutionIdentity()
        context = {
            "user": identity.principal_id,
            "project": identity.project_id,
            "workspace": identity.workspace_id,
            "resource": resource,
            "operation": operation or action,
            "environment": environment or identity.environment,
        }
        constraints = policy.get("constraints", {})
        for key, expected in constraints.items():
            if context.get(key) != expected:
                return PermissionDecision(
                    False, False, "Execution context is not authorized",
                    DecisionOutcome.DENY,
                )

        if not policy.get("allowed", False):
            return PermissionDecision(
                False, False, "Tool is denied by policy", DecisionOutcome.DENY
            )

        if policy.get("approval", False) or action in self.DESTRUCTIVE_ACTIONS:
            return PermissionDecision(
                False, True, "Explicit approval is required",
                DecisionOutcome.REQUIRE_APPROVAL,
            )

        return PermissionDecision(
            policy["allowed"],
            False,
            "Allowed by registered tool policy",
            DecisionOutcome.ALLOW,
        )


if __name__ == "__main__":
    engine = PermissionEngine()

    tests = [
        ("read", "workspace.list", "workspace"),
        ("read", "workspace.list", "system"),
        ("delete", "workspace.list", "workspace"),
        ("read", "unknown.tool", "workspace"),
    ]

    for action, tool, scope in tests:
        result = engine.check(action, tool, scope)
        print(
            f"{tool} | {action} | {scope} "
            f"| allowed={result.allowed} "
            f"| approval={result.requires_approval} "
            f"| {result.reason}"
        )
