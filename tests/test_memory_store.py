import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from memory import store
from security.approval_manager import ApprovalExpiredError, ApprovalManager
from security.idempotency import IdempotencyConflictError, IdempotencyGuard
from security.permission_engine import ExecutionIdentity


class MemoryStoreTests(TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.database_path = Path(temporary_directory.name) / "memory.sqlite"
        patcher = patch.object(store, "DB_PATH", self.database_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        store.initialize()

    def test_additive_initialize_preserves_legacy_task_and_memory_rows(self):
        legacy_path = self.database_path.parent / "legacy.sqlite"
        database = sqlite3.connect(legacy_path)
        try:
            database.executescript("""
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                );
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    event_type TEXT NOT NULL,
                    details TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_key TEXT NOT NULL UNIQUE,
                    memory_value TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO tasks (command) VALUES ('preserve this task');
                INSERT INTO memory (memory_key, memory_value)
                    VALUES ('legacy', 'keep this value');
            """)
        finally:
            database.close()
        with patch.object(store, "DB_PATH", legacy_path):
            store.initialize()
            with store.connect() as database:
                task = database.execute(
                    "SELECT command FROM tasks WHERE id = 1"
                ).fetchone()
                memory = database.execute(
                    "SELECT memory_value FROM memory WHERE memory_key = 'legacy'"
                ).fetchone()
                session_table = database.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' "
                    "AND name = 'sessions'"
                ).fetchone()

        self.assertEqual(task["command"], "preserve this task")
        self.assertEqual(memory["memory_value"], "keep this value")
        self.assertIsNotNone(session_table)

    def test_session_messages_round_trip_structured_tool_messages(self):
        store.create_session("session-1", "Workspace session", "project-1")
        message = {
            "role": "tool",
            "name": "workspace.list",
            "tool_call_id": "call-1",
            "content": "{\"status\":\"success\"}",
        }

        store.append_session_message("session-1", message)

        self.assertEqual(store.get_session_messages("session-1"), [message])
        self.assertEqual(store.get_session("session-1")["project_id"], "project-1")

    def test_operational_history_is_scoped_to_project(self):
        project_task = store.create_task("renderer build decision")
        other_task = store.create_task("renderer unrelated workspace decision")
        store.create_session("project-session", project_id="project-1")
        store.link_task_to_session("project-session", project_task)

        project_history = store.search_task_history(
            "renderer build", project_id="project-1"
        )
        other_project_history = store.search_task_history(
            "renderer build", project_id="project-2"
        )
        unscoped_history = store.search_task_history("renderer build")

        self.assertEqual([item["id"] for item in project_history], [project_task])
        self.assertEqual(other_project_history, [])
        self.assertEqual([item["id"] for item in unscoped_history], [other_task])

    def test_memory_search_is_project_scoped_and_preferences_require_approval(self):
        store.save_memory(
            "project_context", "renderer", "The project uses Blender", "project-1"
        )
        store.save_memory(
            "durable_knowledge", "workspace", "Workspace reads are names only"
        )
        with self.assertRaises(PermissionError):
            store.save_memory(
                "user_preference", "style", "Concise", approved=False
            )
        store.save_memory(
            "user_preference", "style", "Concise", approved=True
        )

        project_results = store.search_memory("Blender", project_id="project-1")
        other_project_results = store.search_memory("Blender", project_id="project-2")
        preference_results = store.search_memory("Concise")

        self.assertEqual([item["memory_key"] for item in project_results], ["renderer"])
        self.assertEqual(other_project_results, [])
        self.assertIn("style", [item["memory_key"] for item in preference_results])

    def test_temporary_memory_is_excluded_after_expiration(self):
        store.save_memory(
            "temporary_context", "active", "Short-lived context", ttl_seconds=60
        )
        with store.connect() as database:
            database.execute(
                "UPDATE memory_items SET expires_at = '2000-01-01T00:00:00+00:00' "
                "WHERE memory_key = 'active'"
            )

        self.assertEqual(store.search_memory("Short-lived"), [])

    def test_approval_state_survives_manager_recreation(self):
        identity = ExecutionIdentity(principal_id="operator-1", project_id="p1")
        arguments = {"resource": "r1"}
        first_manager = ApprovalManager(repository=store)
        request = first_manager.request(
            "resource.read", "read", "resource", arguments, identity
        )

        restarted_manager = ApprovalManager(repository=store)
        restarted_manager.approve(request.approval_id, "reviewer")
        resumed_manager = ApprovalManager(repository=store)

        self.assertTrue(resumed_manager.consume(
            request.approval_id,
            "resource.read",
            "read",
            "resource",
            arguments,
            identity,
        ))
        self.assertFalse(ApprovalManager(repository=store).consume(
            request.approval_id,
            "resource.read",
            "read",
            "resource",
            arguments,
            identity,
        ))

    def test_approval_expiration_persists_across_manager_recreation(self):
        identity = ExecutionIdentity(principal_id="operator-2")
        fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        request = ApprovalManager(repository=store).request(
            "resource.modify",
            "modify",
            "resource",
            {"resource": "r2"},
            identity,
            ttl_seconds=1,
            now=fixed_now,
        )
        restarted_manager = ApprovalManager(repository=store)

        with self.assertRaises(ApprovalExpiredError):
            restarted_manager.approve(
                request.approval_id,
                "reviewer",
                now=fixed_now + timedelta(seconds=2),
            )

        self.assertEqual(
            ApprovalManager(repository=store).get(request.approval_id).status,
            "expired",
        )

    def test_idempotency_state_survives_recreation_and_rejects_conflicts(self):
        first_guard = IdempotencyGuard(repository=store)
        first, reused = first_guard.execute(
            "stable-key",
            lambda: {"status": "success", "result": "persisted"},
            fingerprint="request-fingerprint",
        )
        second, reused_after_restart = IdempotencyGuard(repository=store).execute(
            "stable-key",
            lambda: {"status": "success", "result": "must-not-run"},
            fingerprint="request-fingerprint",
        )

        self.assertEqual(first, second)
        self.assertFalse(reused)
        self.assertTrue(reused_after_restart)
        with self.assertRaises(IdempotencyConflictError):
            IdempotencyGuard(repository=store).execute(
                "stable-key",
                lambda: {"status": "success"},
                fingerprint="different-operation",
            )


if __name__ == "__main__":
    import unittest

    unittest.main()