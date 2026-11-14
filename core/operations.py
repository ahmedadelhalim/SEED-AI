import ctypes
import os
import platform
import shutil
import time
from datetime import datetime, timezone
from typing import Optional

from brain.model_gateway import ModelGateway
from core.service_registry import ServiceRegistry
from core.tool_registry import ToolRegistry
from memory import store


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_uint32),
        ("dwMemoryLoad", ctypes.c_uint32),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


def _system_memory_status():
    if os.name == "nt":
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_status = kernel32.GlobalMemoryStatusEx
        get_status.argtypes = [ctypes.POINTER(_MemoryStatus)]
        get_status.restype = ctypes.c_int
        if not get_status(ctypes.byref(status)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {
            "memory_total_bytes": status.ullTotalPhys,
            "memory_available_bytes": status.ullAvailPhys,
            "memory_load_percent": status.dwMemoryLoad,
        }

    if hasattr(os, "sysconf"):
        page_size = os.sysconf("SC_PAGE_SIZE")
        total_pages = os.sysconf("SC_PHYS_PAGES")
        available_pages = os.sysconf("SC_AVPHYS_PAGES")
        total = page_size * total_pages
        available = page_size * available_pages
        return {
            "memory_total_bytes": total,
            "memory_available_bytes": available,
            "memory_load_percent": round((total - available) * 100 / total),
        }
    raise OSError("System memory metrics are unavailable on this platform")


class OperationsAPI:
    def __init__(self, gateway: ModelGateway, tools: ToolRegistry,
                 services: Optional[ServiceRegistry] = None):
        self.gateway = gateway
        self.tools = tools
        self.services = services or ServiceRegistry()
        self._provider_health = {}
        self._provider_checked_at = None

    def provider_health(self, refresh=False):
        if refresh:
            self._provider_health = self.gateway.health()
            self._provider_checked_at = datetime.now(timezone.utc).isoformat()
        return {
            name: {
                "provider": health.provider,
                "healthy": health.healthy,
                "checked_at": health.checked_at,
                "model_count": health.model_count,
                "error_code": health.error_code,
            }
            for name, health in self._provider_health.items()
        }

    def status(self, refresh_providers=False):
        try:
            from runtime.skills.installer import SkillLifecycleManager
            SkillLifecycleManager.initialize_schema()
            with store.connect() as db:
                skill_rows = db.execute("SELECT state FROM skills_registry").fetchall()
                skills_stats = {
                    "discovered": len(skill_rows),
                    "installed": sum(1 for r in skill_rows if r["state"] == "Installed"),
                    "activated": sum(1 for r in skill_rows if r["state"] == "Activated"),
                }
        except Exception:
            skills_stats = {"discovered": 0, "installed": 0, "activated": 0}

        from core.capabilities import list_capabilities
        return {
            "services": {
                name: {
                    "kind": health.kind,
                    "status": health.status,
                    "checked_at": health.checked_at,
                    "error_code": health.error_code,
                }
                for name, health in self.services.snapshot().items()
            },
            "providers": self.provider_health(refresh=refresh_providers),
            "provider_registry": {
                "default": self.gateway.default_provider,
                "registered": list(self.gateway.provider_names),
            },
            "registered_tools": len(self.tools),
            "skills": skills_stats,
            "creative_capabilities": list_capabilities(),
            "event_cursor": store.latest_event_id(),
            "active_tasks": store.list_tasks(
                statuses=("pending", "running", "approval_required"),
                limit=100,
            ),
        }

    def execution_history(self, limit=50, project_id=None):
        return store.list_tasks(limit=limit, project_id=project_id)

    def audit_history(self, task_id=None, event_types=None, limit=100):
        return store.list_events(task_id, event_types, limit)

    def recent_events(self, limit=100):
        return store.list_events(limit=limit)

    def failures(self, limit=50):
        failed_tasks = store.list_tasks(statuses=("failed",), limit=limit)
        failed_events = store.list_events(
            event_types=("model_request_failed", "tool_failed", "tool_denied", "tool_rejected"),
            limit=limit,
        )
        return {"tasks": failed_tasks, "events": failed_events}

    def pending_approvals(self, limit=50):
        return store.list_approval_requests(status="pending", limit=limit)

    def events_after(self, event_id=0, limit=100):
        return store.list_events_after(event_id=event_id, limit=limit)

    def resource_snapshot(self):
        database_path = store.DB_PATH
        existing_path = database_path.parent
        while not existing_path.exists() and existing_path.parent != existing_path:
            existing_path = existing_path.parent
        disk = shutil.disk_usage(existing_path)
        snapshot = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(),
            "logical_processor_count": os.cpu_count(),
            "disk_total_bytes": disk.total,
            "disk_used_bytes": disk.used,
            "disk_free_bytes": disk.free,
            "process_cpu_seconds": time.process_time(),
            "process_max_rss_bytes": None,
        }
        snapshot.update(_system_memory_status())
        snapshot["memory_used_bytes"] = (
            snapshot["memory_total_bytes"] - snapshot["memory_available_bytes"]
        )
        try:
            import resource

            peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            snapshot["process_max_rss_bytes"] = int(
                peak_rss * (1024 if os.name != "darwin" else 1)
            )
        except (ImportError, AttributeError, OSError):
            pass
        return snapshot