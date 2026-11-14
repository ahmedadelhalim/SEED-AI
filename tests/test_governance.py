from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from security.approval_manager import ApprovalExpiredError, ApprovalManager
from security.idempotency import DuplicateExecutionError, IdempotencyGuard
from security.permission_engine import (
    DecisionOutcome,
    ExecutionIdentity,
    PermissionEngine,
)


class GovernanceTests(TestCase):
    def test_permission_context_is_checked_at_granular_scopes(self):
        policy = {
            "action": "read",
            "scope": "workspace",
            "allowed": True,
            "approval": False,
            "constraints": {
                "user": "user-1",
                "project": "project-1",
                "workspace": "workspace-1",
                "environment": "development",
            },
        }
        identity = ExecutionIdentity(
            principal_id="user-1",
            project_id="project-1",
            workspace_id="workspace-1",
            environment="development",
        )
        with patch.dict(
            PermissionEngine.TOOL_POLICIES,
            {"workspace.list": policy},
            clear=True,
        ):
            engine = PermissionEngine()
            allowed = engine.check("read", "workspace.list", "workspace", identity)
            denied = engine.check(
                "read",
                "workspace.list",
                "workspace",
                ExecutionIdentity(
                    principal_id="user-1",
                    project_id="other-project",
                    workspace_id="workspace-1",
                    environment="development",
                ),
            )

        self.assertEqual(allowed.outcome, DecisionOutcome.ALLOW)
        self.assertEqual(denied.outcome, DecisionOutcome.DENY)
        self.assertFalse(denied.requires_approval)

    def test_destructive_registered_actions_require_approval(self):
        policy = {
            "action": "delete",
            "scope": "resource",
            "allowed": True,
            "approval": False,
        }
        with patch.dict(
            PermissionEngine.TOOL_POLICIES,
            {"resource.delete": policy},
            clear=True,
        ):
            decision = PermissionEngine().check(
                "delete", "resource.delete", "resource"
            )

        self.assertEqual(decision.outcome, DecisionOutcome.REQUIRE_APPROVAL)
        self.assertTrue(decision.requires_approval)
        self.assertFalse(decision.allowed)

    def test_approval_is_explicit_scoped_single_use_and_expires(self):
        manager = ApprovalManager(default_ttl_seconds=60)
        identity = ExecutionIdentity(principal_id="operator-1")
        arguments = {"resource": "item-1", "operation": "delete"}
        request = manager.request(
            "resource.delete", "delete", "resource", arguments, identity
        )

        manager.approve(request.approval_id, "approver-2")
        self.assertFalse(manager.consume(
            request.approval_id,
            "resource.delete",
            "delete",
            "resource",
            {"resource": "item-2", "operation": "delete"},
            identity,
        ))
        self.assertFalse(manager.consume(
            request.approval_id,
            "resource.delete",
            "delete",
            "resource",
            arguments,
            ExecutionIdentity(
                principal_id="operator-1", project_id="different-project"
            ),
        ))
        self.assertTrue(manager.consume(
            request.approval_id,
            "resource.delete",
            "delete",
            "resource",
            arguments,
            identity,
        ))
        self.assertFalse(manager.consume(
            request.approval_id,
            "resource.delete",
            "delete",
            "resource",
            arguments,
            identity,
        ))

        fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        expiring = manager.request(
            "resource.delete",
            "delete",
            "resource",
            arguments,
            identity,
            ttl_seconds=1,
            now=fixed_now,
        )
        with self.assertRaises(ApprovalExpiredError):
            manager.approve(
                expiring.approval_id,
                "approver-2",
                now=fixed_now + timedelta(seconds=2),
            )

    def test_idempotency_guard_caches_completed_operation(self):
        guard = IdempotencyGuard()
        calls = []

        def operation():
            calls.append(True)
            return {"status": "success", "result": 7}

        first, first_reused = guard.execute("operation-1", operation)
        second, second_reused = guard.execute("operation-1", operation)

        self.assertEqual(first, second)
        self.assertFalse(first_reused)
        self.assertTrue(second_reused)
        self.assertEqual(calls, [True])

    def test_idempotency_guard_rejects_reentrant_duplicate(self):
        guard = IdempotencyGuard()

        def operation():
            return guard.execute("operation-2", lambda: None)

        with self.assertRaises(DuplicateExecutionError):
            guard.execute("operation-2", operation)