
from pathlib import Path

from core.task_engine import TaskEngine
from memory.store import connect
from security.permission_engine import PermissionEngine
from runtime.workspace_guard import validate_path, WORKSPACE


class AgentRuntime:
    def __init__(self, tasks=None, permissions=None):
        self.tasks = tasks or TaskEngine()
        self.permissions = permissions or PermissionEngine()

    def record_event(self, task_id, event_type, details):
        with connect() as db:
            db.execute(
                """
                INSERT INTO events (task_id, event_type, details)
                VALUES (?, ?, ?)
                """,
                (task_id, event_type, details)
            )

    def list_workspace(self, relative_path="."):
        task = self.tasks.submit(
            f"List workspace directory: {relative_path}"
        )
        task_id = task["task_id"]
        self.tasks.set_status(task_id, "running")

        try:
            decision = self.permissions.check(
                "read",
                "workspace.list",
                "workspace"
            )

            if not decision.allowed:
                self.record_event(
                    task_id, "permission_denied", decision.reason
                )
                self.tasks.set_status(task_id, "failed")
                return {"status": "denied", "reason": decision.reason}

            target = validate_path(relative_path)

            if not target.exists():
                self.tasks.set_status(task_id, "failed")
                raise FileNotFoundError(relative_path)

            if not target.is_dir():
                self.tasks.set_status(task_id, "failed")
                raise NotADirectoryError(relative_path)

            # Listing names only: no file contents are opened.
            entries = sorted(
                (
                    {
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file"
                    }
                    for item in target.iterdir()
                ),
                key=lambda item: (item["type"], item["name"].lower())
            )

            self.record_event(
                task_id,
                "workspace_listed",
                f"Listed {len(entries)} entries in workspace"
            )
            self.tasks.set_status(task_id, "completed")

            return {
                "status": "success",
                "task_id": task_id,
                "entries": entries
            }

        except (PermissionError, OSError, ValueError) as error:
            self.record_event(
                task_id, "workspace_access_denied", str(error)
            )
            self.tasks.set_status(task_id, "failed")
            return {
                "status": "denied",
                "task_id": task_id,
                "reason": str(error)
            }

    def list_workspace_entries(self, relative_path="."):
        target = validate_path(relative_path)
        if not target.exists():
            raise FileNotFoundError(relative_path)
        if not target.is_dir():
            raise NotADirectoryError(relative_path)
        return {
            "status": "success",
            "entries": sorted(
                ({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                } for item in target.iterdir()),
                key=lambda item: (item["type"], item["name"].lower()),
            ),
        }


if __name__ == "__main__":
    agent = AgentRuntime()
    result = agent.list_workspace(".")

    print("AGENT_RUNTIME_TEST")
    print("STATUS:", result["status"])
    print("TASK_ID:", result.get("task_id"))
    print("ENTRIES:")

    for entry in result.get("entries", []):
        print(f"- {entry['type']}: {entry['name']}")
