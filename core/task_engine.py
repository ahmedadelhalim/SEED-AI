
from memory.store import (
    acquire_task_lease,
    create_task,
    get_task,
    initialize,
    reconcile_orphaned_tasks,
    record_event,
    release_task_lease,
    update_task_status,
)


class TaskEngine:
    def __init__(self, reconcile_on_startup: bool = False):
        initialize()
        if reconcile_on_startup:
            self.reconcile_orphaned_tasks()

    def submit(self, command: str, lease_owner: str = None, lease_seconds: int = None):
        command = command.strip()

        if not command:
            raise ValueError("Command cannot be empty")

        task_id = create_task(command, lease_owner=lease_owner, lease_seconds=lease_seconds)
        task = get_task(task_id)

        return {
            "task_id": task["id"],
            "command": task["command"],
            "status": task["status"],
            "created_at": task["created_at"],
        }

    def get(self, task_id: int):
        task = get_task(task_id)
        if not task:
            return None
        return dict(task)

    def set_status(self, task_id: int, status: str, details: str = None):
        update_task_status(task_id, status, details=details)

    def acquire_lease(self, task_id: int, lease_owner: str, lease_seconds: int = 120, now=None):
        return acquire_task_lease(task_id, lease_owner, lease_seconds=lease_seconds, now=now)

    def release_lease(self, task_id: int, lease_owner: str):
        return release_task_lease(task_id, lease_owner)

    def record_event(self, task_id: int, event_type: str, details: str):
        record_event(task_id, event_type, details)

    def reconcile_orphaned_tasks(self, stale_running_seconds: float = 120,
                                 stale_pending_seconds: float = 300, now=None):
        return reconcile_orphaned_tasks(
            stale_running_seconds=stale_running_seconds,
            stale_pending_seconds=stale_pending_seconds,
            now=now,
        )


def main():
    engine = TaskEngine()
    result = engine.submit("SEED task engine verification")

    print("TASK_ENGINE_OPERATIONAL")
    print("TASK_ID:", result["task_id"])
    print("COMMAND:", result["command"])
    print("STATUS:", result["status"])


if __name__ == "__main__":
    main()
