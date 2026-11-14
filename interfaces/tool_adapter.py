from typing import Any, Mapping, Optional

from core.task_engine import TaskEngine
from core.tool_registry import ToolError, ToolRegistry
from memory import store
from security.approval_manager import ApprovalManager
from security.permission_engine import (
    DecisionOutcome,
    ExecutionIdentity,
    PermissionEngine,
)


class MCPToolAdapter:
    def __init__(self, tools: ToolRegistry, permissions: PermissionEngine,
                 tasks: TaskEngine, approvals: Optional[ApprovalManager] = None):
        self.tools = tools
        self.permissions = permissions
        self.tasks = tasks
        self.approvals = approvals or ApprovalManager(repository=store)

    def invoke(self, name: str, arguments: Mapping[str, Any],
               identity: Optional[ExecutionIdentity] = None,
               approval_id: Optional[str] = None):
        identity = identity or ExecutionIdentity()
        task = self.tasks.submit("MCP tool request: " + name)
        task_id = task["task_id"]
        tool = self.tools.get(name)
        if tool is None:
            self.tasks.record_event(task_id, "tool_denied", "Unregistered tool requested")
            self.tasks.set_status(task_id, "failed")
            return {"status": "denied", "reason": "Tool is not registered"}

        try:
            tool.validate_arguments(arguments)
        except ToolError:
            self.tasks.record_event(task_id, "tool_rejected", "Invalid tool arguments")
            self.tasks.set_status(task_id, "failed")
            return {"status": "invalid_arguments"}

        decision = self.permissions.check(
            tool.action,
            tool.name,
            tool.scope,
            identity=identity,
            resource=arguments.get("resource"),
            operation=tool.action,
            environment=identity.environment,
        )
        outcome = decision.outcome or (
            DecisionOutcome.ALLOW if decision.allowed
            else DecisionOutcome.REQUIRE_APPROVAL if decision.requires_approval
            else DecisionOutcome.DENY
        )
        self.tasks.record_event(
            task_id, "permission_decision", tool.name + ":" + outcome.value
        )
        if outcome == DecisionOutcome.DENY:
            self.tasks.record_event(task_id, "tool_denied", decision.reason)
            self.tasks.set_status(task_id, "failed")
            return {"status": "denied", "reason": decision.reason}

        if outcome == DecisionOutcome.REQUIRE_APPROVAL:
            approved = bool(approval_id) and self.approvals.consume(
                approval_id, tool.name, tool.action, tool.scope, arguments, identity
            )
            if not approved:
                request = self.approvals.request(
                    tool.name, tool.action, tool.scope, arguments, identity
                )
                self.tasks.record_event(task_id, "approval_required", tool.name)
                self.tasks.set_status(task_id, "approval_required")
                return {
                    "status": "approval_required",
                    "approval_id": request.approval_id,
                    "expires_at": request.expires_at.isoformat(),
                }

        self.tasks.set_status(task_id, "running")
        try:
            result = tool.handler(**dict(arguments))
        except Exception as error:
            self.tasks.record_event(task_id, "tool_failed", type(error).__name__)
            self.tasks.set_status(task_id, "failed")
            return {"status": "failed", "error": "Tool execution failed"}

        self.tasks.record_event(task_id, "tool_completed", tool.name)
        self.tasks.set_status(task_id, "completed")
        return result