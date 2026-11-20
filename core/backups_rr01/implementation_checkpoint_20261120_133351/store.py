import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get(
    "SEED_DATABASE_PATH", "D:/SEED-AI/data/seed_memory.db"
))


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exception_type, exception, traceback):
        try:
            return super().__exit__(exception_type, exception, traceback)
        finally:
            self.close()


def _parse_timestamp(val):
    if not val:
        return None
    val = str(val).strip().replace("T", " ")
    if val.endswith("Z"):
        val = val[:-1]
    if "+" in val:
        val = val.split("+")[0]
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(val, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def get_db_path() -> Path:
    path = Path(os.environ.get(
        "SEED_DATABASE_PATH", "D:/SEED-AI/data/seed_memory.db"
    ))
    if os.environ.get("SEED_TEST_MODE") == "1":
        prod_path = Path("D:/SEED-AI/data/seed_memory.db").resolve()
        if path.resolve() == prod_path:
            raise RuntimeError("CRITICAL SECURITY VIOLATION: Attempted to open production database during test mode!")
    return path


def connect():
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000;")
    return connection


def initialize():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            lease_owner TEXT,
            lease_expires_at TEXT
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            event_type TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        );

        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_key TEXT NOT NULL UNIQUE,
            memory_value TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            project_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS session_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS session_tasks (
            session_id TEXT NOT NULL,
            task_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(session_id, task_id),
            FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        );

        CREATE TABLE IF NOT EXISTS memory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_type TEXT NOT NULL CHECK (memory_type IN (
                'durable_knowledge', 'user_preference',
                'project_context', 'temporary_context'
            )),
            memory_key TEXT NOT NULL,
            content TEXT NOT NULL,
            project_id TEXT NOT NULL DEFAULT '',
            approved INTEGER NOT NULL DEFAULT 0,
            expires_at TEXT,
            source_task_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(memory_type, project_id, memory_key),
            FOREIGN KEY(source_task_id) REFERENCES tasks(id)
        );

        CREATE TABLE IF NOT EXISTS approval_requests (
            approval_id TEXT PRIMARY KEY,
            principal_id TEXT NOT NULL,
            identity_digest TEXT NOT NULL,
            identity_json TEXT NOT NULL,
            tool TEXT NOT NULL,
            action TEXT NOT NULL,
            scope TEXT NOT NULL,
            arguments_digest TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            approved_by TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS idempotency_records (
            idempotency_key TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed')),
            result_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_session_messages_session
            ON session_messages(session_id, id);
        CREATE INDEX IF NOT EXISTS idx_memory_items_project_type
            ON memory_items(project_id, memory_type, updated_at);

        CREATE TABLE IF NOT EXISTS plans (
            plan_id TEXT PRIMARY KEY,
            objective TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS plan_steps (
            plan_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            name TEXT NOT NULL,
            dependencies_json TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending',
            result_json TEXT,
            evidence_json TEXT NOT NULL DEFAULT '[]',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(plan_id, step_id),
            FOREIGN KEY(plan_id) REFERENCES plans(plan_id) ON DELETE CASCADE
        );
        """)

        cursor = db.execute("PRAGMA table_info(tasks)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "updated_at" not in columns:
            try:
                db.execute("ALTER TABLE tasks ADD COLUMN updated_at TEXT")
                db.execute(
                    "UPDATE tasks SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                    "WHERE updated_at IS NULL"
                )
            except sqlite3.OperationalError:
                pass
        if "lease_owner" not in columns:
            try:
                db.execute("ALTER TABLE tasks ADD COLUMN lease_owner TEXT")
            except sqlite3.OperationalError:
                pass
        if "lease_expires_at" not in columns:
            try:
                db.execute("ALTER TABLE tasks ADD COLUMN lease_expires_at TEXT")
            except sqlite3.OperationalError:
                pass


def create_task(command, lease_owner=None, lease_seconds=None):
    with connect() as db:
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        lease_expires = (
            (now_dt + timedelta(seconds=lease_seconds)).strftime("%Y-%m-%d %H:%M:%S")
            if lease_seconds else None
        )
        try:
            cursor = db.execute(
                """
                INSERT INTO tasks (command, status, updated_at, lease_owner, lease_expires_at)
                VALUES (?, 'pending', ?, ?, ?)
                """,
                (command, now_str, lease_owner, lease_expires),
            )
        except sqlite3.OperationalError:
            cursor = db.execute(
                "INSERT INTO tasks (command) VALUES (?)",
                (command,),
            )
        task_id = cursor.lastrowid

        db.execute(
            "INSERT INTO events (task_id, event_type, details) VALUES (?, ?, ?)",
            (task_id, "task_created", "Task recorded successfully"),
        )
        return task_id


def get_task(task_id):
    with connect() as db:
        return db.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()


def update_task_status(task_id, status, details=None):
    allowed_statuses = {
        "pending", "running", "approval_required", "completed",
        "failed", "cancelled", "interrupted",
    }
    if status not in allowed_statuses:
        raise ValueError(f"Unsupported task status: {status}")

    with connect() as db:
        row = db.execute(
            "SELECT status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Task {task_id} not found")
        current_status = row["status"]

        if current_status == status:
            if current_status == "completed":
                raise ValueError(f"Duplicate completion: Task {task_id} is already completed")
            try:
                db.execute(
                    "UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (task_id,),
                )
            except sqlite3.OperationalError:
                pass
            return

        terminal_statuses = {"completed", "failed", "cancelled", "interrupted"}
        if current_status in terminal_statuses:
            raise ValueError(
                f"Cannot transition task {task_id} from terminal state '{current_status}' to '{status}'"
            )

        valid_transitions = {
            "pending": {"running", "approval_required", "cancelled", "interrupted", "failed", "completed"},
            "running": {"approval_required", "completed", "failed", "cancelled", "interrupted"},
            "approval_required": {"running", "completed", "failed", "cancelled", "interrupted"},
        }

        if status not in valid_transitions.get(current_status, set()):
            raise ValueError(
                f"Invalid task status transition from '{current_status}' to '{status}'"
            )

        completed_at = "CURRENT_TIMESTAMP" if status in terminal_statuses else "NULL"

        try:
            db.execute(
                f"UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP, "
                f"completed_at = {completed_at} WHERE id = ?",
                (status, task_id),
            )
        except sqlite3.OperationalError:
            db.execute(
                f"UPDATE tasks SET status = ?, completed_at = {completed_at} WHERE id = ?",
                (status, task_id),
            )

        if details:
            db.execute(
                "INSERT INTO events (task_id, event_type, details) VALUES (?, ?, ?)",
                (task_id, f"task_{status}", details),
            )


def acquire_task_lease(task_id, lease_owner, lease_seconds=120, now=None):
    if not lease_owner:
        raise ValueError("lease_owner is required")
    current_dt = now or datetime.now(timezone.utc)
    current_str = current_dt.strftime("%Y-%m-%d %H:%M:%S")
    expires_str = (current_dt + timedelta(seconds=lease_seconds)).strftime("%Y-%m-%d %H:%M:%S")
    with connect() as db:
        cursor = db.execute(
            """
            UPDATE tasks
            SET lease_owner = ?, lease_expires_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status IN ('pending', 'running')
              AND (lease_owner IS NULL OR lease_owner = ? OR lease_expires_at <= ?)
            """,
            (lease_owner, expires_str, task_id, lease_owner, current_str),
        )
        return cursor.rowcount > 0


def release_task_lease(task_id, lease_owner):
    with connect() as db:
        cursor = db.execute(
            """
            UPDATE tasks
            SET lease_owner = NULL, lease_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND lease_owner = ?
            """,
            (task_id, lease_owner),
        )
        return cursor.rowcount > 0


def reconcile_orphaned_tasks(stale_running_seconds=120, stale_pending_seconds=300, now=None):
    current_dt = now or datetime.now(timezone.utc)
    reconciled = []

    with connect() as db:
        try:
            rows = db.execute(
                """
                SELECT id, command, status, created_at,
                       COALESCE(updated_at, created_at) AS last_active,
                       lease_owner, lease_expires_at
                FROM tasks WHERE status IN ('pending', 'running')
                """
            ).fetchall()
        except sqlite3.OperationalError:
            rows = db.execute(
                "SELECT id, command, status, created_at FROM tasks WHERE status IN ('pending', 'running')"
            ).fetchall()

        for row in rows:
            task_id = row["id"]
            status = row["status"]
            created_at = _parse_timestamp(row["created_at"])
            last_active = (
                _parse_timestamp(row["last_active"])
                if "last_active" in row.keys() else created_at
            ) or created_at
            lease_expires = (
                _parse_timestamp(row["lease_expires_at"])
                if "lease_expires_at" in row.keys() and row["lease_expires_at"] else None
            )
            lease_owner = row["lease_owner"] if "lease_owner" in row.keys() else None

            is_orphaned = False
            reason = ""

            if status == "running":
                if lease_expires and lease_expires < current_dt:
                    is_orphaned = True
                    reason = f"Execution lease expired at {row['lease_expires_at']}"
                elif created_at and (current_dt - (last_active or created_at)).total_seconds() > stale_running_seconds:
                    is_orphaned = True
                    inactive_secs = int((current_dt - (last_active or created_at)).total_seconds())
                    reason = f"Running task inactive for {inactive_secs}s (threshold {stale_running_seconds}s)"
                elif not lease_owner:
                    is_orphaned = True
                    reason = "Running task has no active worker lease across restart"

            elif status == "pending":
                if lease_expires and lease_expires < current_dt:
                    is_orphaned = True
                    reason = f"Pending task lease expired at {row['lease_expires_at']}"
                elif created_at and (current_dt - created_at).total_seconds() > stale_pending_seconds:
                    is_orphaned = True
                    untouched_secs = int((current_dt - created_at).total_seconds())
                    reason = f"Pending task untouched for {untouched_secs}s (threshold {stale_pending_seconds}s)"

            if is_orphaned:
                try:
                    db.execute(
                        """
                        UPDATE tasks
                        SET status = 'interrupted', completed_at = CURRENT_TIMESTAMP,
                            lease_owner = NULL, lease_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (task_id,),
                    )
                except sqlite3.OperationalError:
                    db.execute(
                        "UPDATE tasks SET status = 'interrupted', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (task_id,),
                    )
                db.execute(
                    "INSERT INTO events (task_id, event_type, details) VALUES (?, ?, ?)",
                    (task_id, "task_interrupted", reason),
                )
                reconciled.append({
                    "task_id": task_id,
                    "previous_status": status,
                    "new_status": "interrupted",
                    "reason": reason,
                })

    return reconciled


def record_event(task_id, event_type, details):
    with connect() as db:
        db.execute(
            "INSERT INTO events (task_id, event_type, details) VALUES (?, ?, ?)",
            (task_id, event_type, details),
        )


def get_task_events(task_id):
    with connect() as db:
        return db.execute(
            "SELECT * FROM events WHERE task_id = ? ORDER BY id", (task_id,)
        ).fetchall()


def create_session(session_id, title="", project_id=None):
    if not session_id:
        raise ValueError("Session ID is required")
    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)",
            (session_id,),
        )
        db.execute(
            "UPDATE sessions SET title = CASE WHEN ? = '' THEN title ELSE ? END, "
            "project_id = CASE WHEN ? IS NULL THEN project_id ELSE ? END, "
            "status = 'active', updated_at = CURRENT_TIMESTAMP "
            "WHERE session_id = ?",
            (title, title, project_id, project_id or "", session_id),
        )


def link_task_to_session(session_id, task_id):
    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO session_tasks (session_id, task_id) VALUES (?, ?)",
            (session_id, task_id),
        )


def append_session_message(session_id, message):
    if not isinstance(message, dict) or message.get("role") not in {
        "system", "user", "assistant", "tool",
    }:
        raise ValueError("Session message has an unsupported role")
    encoded = json.dumps(message, ensure_ascii=True, separators=(",", ":"))
    with connect() as db:
        db.execute(
            "INSERT INTO session_messages (session_id, role, message_json) "
            "VALUES (?, ?, ?)",
            (session_id, message["role"], encoded),
        )
        db.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
            (session_id,),
        )


def get_session_messages(session_id, limit=50):
    if limit < 1:
        raise ValueError("Message limit must be positive")
    with connect() as db:
        rows = db.execute(
            "SELECT message_json FROM session_messages WHERE session_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [json.loads(row["message_json"]) for row in reversed(rows)]


def set_session_status(session_id, status):
    if status not in {"active", "awaiting_approval", "completed", "failed", "cancelled"}:
        raise ValueError("Unsupported session status")
    with connect() as db:
        db.execute(
            "UPDATE sessions SET status = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE session_id = ?",
            (status, session_id),
        )


def get_session(session_id):
    with connect() as db:
        return db.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()


def save_memory(memory_type, memory_key, content, project_id=None,
                approved=False, source_task_id=None, ttl_seconds=None):
    allowed_types = {
        "durable_knowledge", "user_preference", "project_context",
        "temporary_context",
    }
    if memory_type not in allowed_types:
        raise ValueError("Unsupported memory type")
    if not memory_key or not isinstance(content, str):
        raise ValueError("Memory key and string content are required")
    if memory_type == "user_preference" and not approved:
        raise PermissionError("User preferences require explicit approval")
    if memory_type == "project_context" and not project_id:
        raise ValueError("Project context requires a project ID")

    expires_at = None
    if memory_type == "temporary_context":
        lifetime = 3600 if ttl_seconds is None else ttl_seconds
        if lifetime < 1:
            raise ValueError("Temporary memory lifetime must be positive")
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=lifetime)).isoformat()

    project = project_id or ""
    with connect() as db:
        existing = db.execute(
            "SELECT id FROM memory_items WHERE memory_type = ? AND project_id = ? "
            "AND memory_key = ?",
            (memory_type, project, memory_key),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE memory_items SET content = ?, approved = ?, expires_at = ?, "
                "source_task_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (content, int(approved), expires_at, source_task_id, existing["id"]),
            )
        else:
            db.execute(
                "INSERT INTO memory_items (memory_type, memory_key, content, "
                "project_id, approved, expires_at, source_task_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (memory_type, memory_key, content, project, int(approved),
                 expires_at, source_task_id),
            )


def get_memory(memory_type, memory_key, project_id=None):
    with connect() as db:
        return db.execute(
            "SELECT * FROM memory_items WHERE memory_type = ? AND project_id = ? "
            "AND memory_key = ?",
            (memory_type, project_id or "", memory_key),
        ).fetchone()


def search_memory(query, project_id=None, limit=8):
    if limit < 1:
        raise ValueError("Memory result limit must be positive")
    terms = re.findall(r"[\w-]+", (query or "").lower())[:8]
    conditions = [
        "(project_id = '' OR project_id = ?)",
        "(expires_at IS NULL OR expires_at > ?)",
        "(memory_type != 'user_preference' OR approved = 1)",
    ]
    parameters = [project_id or "", datetime.now(timezone.utc).isoformat()]
    if terms:
        conditions.append("(" + " OR ".join(
            "LOWER(memory_key) LIKE ? OR LOWER(content) LIKE ?" for _ in terms
        ) + ")")
        for term in terms:
            pattern = "%" + term + "%"
            parameters.extend((pattern, pattern))
    parameters.append(limit)
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM memory_items WHERE " + " AND ".join(conditions)
            + " ORDER BY CASE WHEN project_id = ? THEN 0 ELSE 1 END, "
            "approved DESC, updated_at DESC LIMIT ?",
            parameters[:-1] + [project_id or "", parameters[-1]],
        ).fetchall()
    return [dict(row) for row in rows]


def search_task_history(query, project_id=None, limit=5):
    if limit < 1:
        raise ValueError("History result limit must be positive")
    terms = re.findall(r"[\w-]+", (query or "").lower())[:8]
    conditions = []
    parameters = []
    if project_id is None:
        conditions.append("(s.project_id IS NULL OR s.project_id = '')")
    else:
        conditions.append("s.project_id = ?")
        parameters.append(project_id)
    if terms:
        conditions.append("(" + " OR ".join(
            "LOWER(t.command) LIKE ? OR LOWER(COALESCE(e.details, '')) LIKE ?"
            for _ in terms
        ) + ")")
        for term in terms:
            pattern = "%" + term + "%"
            parameters.extend((pattern, pattern))
    parameters.append(limit)
    with connect() as db:
        rows = db.execute(
            "SELECT t.id, t.command, t.status, t.created_at, "
            "GROUP_CONCAT(e.event_type, ',') AS event_types "
            "FROM tasks t LEFT JOIN session_tasks st ON st.task_id = t.id "
            "LEFT JOIN sessions s ON s.session_id = st.session_id "
            "LEFT JOIN events e ON e.task_id = t.id WHERE "
            + " AND ".join(conditions)
            + " GROUP BY t.id ORDER BY t.id DESC LIMIT ?",
            parameters,
        ).fetchall()
    return [dict(row) for row in rows]


def save_approval_request(approval):
    with connect() as db:
        db.execute(
            "INSERT INTO approval_requests (approval_id, principal_id, "
            "identity_digest, identity_json, tool, action, scope, arguments_digest, "
            "status, approved_by, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                approval["approval_id"], approval["principal_id"],
                approval["identity_digest"], approval["identity_json"],
                approval["tool"], approval["action"], approval["scope"],
                approval["arguments_digest"], approval["status"],
                approval.get("approved_by"), approval["created_at"],
                approval["expires_at"],
            ),
        )


def get_approval_request(approval_id):
    with connect() as db:
        row = db.execute(
            "SELECT * FROM approval_requests WHERE approval_id = ?",
            (approval_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def update_approval_status(approval_id, status, approved_by=None):
    allowed_statuses = {"pending", "approved", "consumed", "expired"}
    if status not in allowed_statuses:
        raise ValueError("Unsupported approval status")
    with connect() as db:
        db.execute(
            "UPDATE approval_requests SET status = ?, approved_by = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE approval_id = ?",
            (status, approved_by, approval_id),
        )


def approve_request(approval_id, approved_by, now):
    with connect() as db:
        db.execute(
            "UPDATE approval_requests SET status = CASE "
            "WHEN expires_at <= ? THEN 'expired' ELSE 'approved' END, "
            "approved_by = CASE WHEN expires_at <= ? THEN NULL ELSE ? END, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE approval_id = ? AND status = 'pending'",
            (now, now, approved_by, approval_id),
        )
    return get_approval_request(approval_id)


def consume_approval_request(approval_id, principal_id, identity_digest,
                             tool, action, scope, arguments_digest, now):
    with connect() as db:
        db.execute(
            "UPDATE approval_requests SET status = 'expired', "
            "updated_at = CURRENT_TIMESTAMP WHERE approval_id = ? "
            "AND status = 'approved' AND expires_at <= ?",
            (approval_id, now),
        )
        cursor = db.execute(
            "UPDATE approval_requests SET status = 'consumed', "
            "updated_at = CURRENT_TIMESTAMP WHERE approval_id = ? "
            "AND principal_id = ? AND identity_digest = ? AND tool = ? "
            "AND action = ? AND scope = ? AND arguments_digest = ? "
            "AND status = 'approved' AND expires_at > ?",
            (approval_id, principal_id, identity_digest, tool, action, scope,
             arguments_digest, now),
        )
    return cursor.rowcount == 1


def claim_idempotency(idempotency_key, fingerprint):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT fingerprint, status, result_json FROM idempotency_records "
            "WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if row is None:
            db.execute(
                "INSERT INTO idempotency_records "
                "(idempotency_key, fingerprint, status) VALUES (?, ?, 'in_progress')",
                (idempotency_key, fingerprint),
            )
            return "claimed", None
        if row["fingerprint"] != fingerprint:
            return "conflict", None
        if row["status"] == "completed":
            return "completed", json.loads(row["result_json"])
        return "in_progress", None


def complete_idempotency(idempotency_key, fingerprint, result):
    encoded = json.dumps(result, ensure_ascii=True, separators=(",", ":"))
    with connect() as db:
        db.execute(
            "UPDATE idempotency_records SET status = 'completed', result_json = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE idempotency_key = ? "
            "AND fingerprint = ? AND status = 'in_progress'",
            (encoded, idempotency_key, fingerprint),
        )


def release_idempotency(idempotency_key, fingerprint):
    with connect() as db:
        db.execute(
            "DELETE FROM idempotency_records WHERE idempotency_key = ? "
            "AND fingerprint = ? AND status = 'in_progress'",
            (idempotency_key, fingerprint),
        )


def list_tasks(statuses=None, limit=50, project_id=None):
    if limit < 1:
        raise ValueError("Task result limit must be positive")
    conditions = []
    parameters = []
    if statuses:
        allowed_statuses = {
            "pending", "running", "approval_required", "completed",
            "failed", "cancelled",
        }
        if any(status not in allowed_statuses for status in statuses):
            raise ValueError("Unsupported task status filter")
        conditions.append("t.status IN (" + ",".join("?" for _ in statuses) + ")")
        parameters.extend(statuses)
    if project_id is not None:
        conditions.append("s.project_id = ?")
        parameters.append(project_id)
    query = (
        "SELECT t.*, GROUP_CONCAT(DISTINCT s.project_id) AS project_ids "
        "FROM tasks t LEFT JOIN session_tasks st ON st.task_id = t.id "
        "LEFT JOIN sessions s ON s.session_id = st.session_id"
    )
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " GROUP BY t.id ORDER BY t.id DESC LIMIT ?"
    parameters.append(limit)
    with connect() as db:
        rows = db.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


def list_events(task_id=None, event_types=None, limit=100):
    if limit < 1:
        raise ValueError("Event result limit must be positive")
    conditions = []
    parameters = []
    if task_id is not None:
        conditions.append("task_id = ?")
        parameters.append(task_id)
    if event_types:
        conditions.append(
            "event_type IN (" + ",".join("?" for _ in event_types) + ")"
        )
        parameters.extend(event_types)
    query = "SELECT * FROM events"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id DESC LIMIT ?"
    parameters.append(limit)
    with connect() as db:
        rows = db.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


def list_events_after(event_id=0, limit=100):
    if event_id < 0 or limit < 1:
        raise ValueError("Event cursor and limit are invalid")
    with connect() as db:
        rows = db.execute(
            "SELECT id, task_id, event_type, created_at, "
            "CASE WHEN event_type = 'permission_decision' "
            "THEN substr(details, instr(details, ':') + 1) ELSE NULL END AS decision "
            "FROM events "
            "WHERE id > ? ORDER BY id ASC LIMIT ?",
            (event_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def latest_event_id():
    with connect() as db:
        row = db.execute("SELECT COALESCE(MAX(id), 0) AS event_id FROM events").fetchone()
    return row["event_id"]


def list_approval_requests(status="pending", limit=50):
    if limit < 1:
        raise ValueError("Approval result limit must be positive")
    allowed_statuses = {"pending", "approved", "consumed", "expired"}
    if status is not None and status not in allowed_statuses:
        raise ValueError("Unsupported approval status filter")
    query = (
        "SELECT approval_id, principal_id, tool, action, scope, status, "
        "approved_by, created_at, expires_at FROM approval_requests"
    )
    parameters = []
    if status is not None:
        query += " WHERE status = ?"
        parameters.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    parameters.append(limit)
    with connect() as db:
        rows = db.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


def create_plan(plan_id, objective, steps):
    if not plan_id or not objective:
        raise ValueError("Plan ID and objective are required")
    with connect() as db:
        db.execute("INSERT INTO plans (plan_id, objective) VALUES (?, ?)", (plan_id, objective))
        for step in steps:
            db.execute(
                "INSERT INTO plan_steps (plan_id, step_id, name, dependencies_json, metadata_json) VALUES (?, ?, ?, ?, ?)",
                (
                    plan_id, step["step_id"], step["name"],
                    json.dumps(list(step.get("dependencies", ()))),
                    json.dumps({key: step[key] for key in ("tool", "arguments", "expected_result", "verification", "risk") if key in step}),
                ),
            )


def get_plan(plan_id):
    with connect() as db:
        plan = db.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,)).fetchone()
        if plan is None:
            return None
        steps = db.execute("SELECT * FROM plan_steps WHERE plan_id = ? ORDER BY rowid", (plan_id,)).fetchall()
    return {
        **dict(plan),
        "steps": [{
            **dict(step),
            "dependencies": json.loads(step["dependencies_json"]),
            "result": json.loads(step["result_json"]) if step["result_json"] else None,
            "evidence": json.loads(step["evidence_json"]),
            "metadata": json.loads(step["metadata_json"]),
        } for step in steps],
    }


def update_plan_step(plan_id, step_id, state, result=None, evidence=()):
    if state not in {"pending", "running", "completed", "failed", "blocked", "cancelled"}:
        raise ValueError("Unsupported plan step state")
    with connect() as db:
        cursor = db.execute(
            "UPDATE plan_steps SET state = ?, result_json = ?, evidence_json = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE plan_id = ? AND step_id = ? AND state != 'completed'",
            (state, json.dumps(result) if result is not None else None, json.dumps(list(evidence)), plan_id, step_id),
        )
        db.execute("UPDATE plans SET updated_at = CURRENT_TIMESTAMP WHERE plan_id = ?", (plan_id,))
    refresh_plan_state(plan_id)
    return cursor.rowcount == 1


def block_dependent_plan_steps(plan_id, failed_step_id):
    plan = get_plan(plan_id)
    if plan is None:
        return
    with connect() as db:
        for step in plan["steps"]:
            if failed_step_id in step["dependencies"] and step["state"] == "pending":
                db.execute("UPDATE plan_steps SET state = 'blocked', updated_at = CURRENT_TIMESTAMP WHERE plan_id = ? AND step_id = ?", (plan_id, step["step_id"]))
    refresh_plan_state(plan_id)


def cancel_plan(plan_id):
    plan = get_plan(plan_id)
    if plan is None:
        raise KeyError(plan_id)
    with connect() as db:
        db.execute(
            "UPDATE plan_steps SET state = 'cancelled', updated_at = CURRENT_TIMESTAMP "
            "WHERE plan_id = ? AND state IN ('pending', 'running')",
            (plan_id,),
        )
    return refresh_plan_state(plan_id)


def refresh_plan_state(plan_id):
    plan = get_plan(plan_id)
    if plan is None:
        return None
    states = {step["state"] for step in plan["steps"]}
    if states == {"completed"}:
        state = "completed"
    elif "failed" in states:
        state = "failed"
    elif "blocked" in states:
        state = "blocked"
    elif "running" in states:
        state = "running"
    elif "cancelled" in states:
        state = "cancelled"
    else:
        state = "pending"
    with connect() as db:
        db.execute("UPDATE plans SET state = ?, updated_at = CURRENT_TIMESTAMP WHERE plan_id = ?", (state, plan_id))
    return state


if __name__ == "__main__":
    initialize()
    task_id = create_task("SEED memory persistence verification")
    task = get_task(task_id)

    print("TASK_CREATED:", task["id"])
    print("TASK_STATUS:", task["status"])
    print("TASK_COMMAND:", task["command"])
    print("MEMORY_PERSISTENCE_OK")
