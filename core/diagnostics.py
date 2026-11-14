"""
SEED Intelligent Self-Diagnostics & System Awareness
Performs read-only telemetry and health checks across services, models, memory, database, and tasks.
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from memory import store
from core.service_registry import ServiceRegistry
from brain.model_gateway import ModelGateway


class SystemDiagnostics:
    """Performs comprehensive health checks and diagnostics across SEED subsystems."""

    @staticmethod
    def inspect_system(services: Optional[ServiceRegistry] = None, gateway: Optional[ModelGateway] = None) -> Dict[str, Any]:
        report = {
            "database_health": False,
            "memory_available": False,
            "services": {},
            "model_provider": "unknown",
            "provider_healthy": False,
            "interrupted_tasks": 0,
            "pending_approvals": 0,
            "diagnostics": [],
        }

        # 1. Database Health Check
        try:
            with store.connect() as db:
                db.execute("SELECT 1").fetchone()
            report["database_health"] = True
        except Exception as err:
            report["diagnostics"].append({"component": "database", "issue": str(err), "severity": "critical"})

        # 2. Memory Availability Check
        try:
            store.search_memory("test", limit=1)
            report["memory_available"] = True
        except Exception as err:
            report["diagnostics"].append({"component": "memory", "issue": str(err), "severity": "high"})

        # 3. Services Check
        if services:
            try:
                snapshot = services.snapshot()
                report["services"] = snapshot
                unhealthy = [name for name, info in snapshot.items() if info.get("status") != "healthy"]
                if unhealthy:
                    report["diagnostics"].append({"component": "services", "issue": f"Unhealthy services: {unhealthy}", "severity": "medium"})
            except Exception as err:
                report["diagnostics"].append({"component": "services", "issue": str(err), "severity": "medium"})

        # 4. Model Provider & Gateway Check
        try:
            gw = gateway or ModelGateway.with_local_defaults()
            default_prov = gw.default_provider
            report["model_provider"] = default_prov
            provider_obj = gw.get_provider(default_prov)
            models = provider_obj.list_models()
            report["provider_healthy"] = len(models) > 0
            if not report["provider_healthy"]:
                report["diagnostics"].append({"component": "model_provider", "issue": "No models available from provider", "severity": "high"})
        except Exception as err:
            report["diagnostics"].append({"component": "model_gateway", "issue": str(err), "severity": "high"})

        # 5. Task & Approval Telemetry
        try:
            with store.connect() as db:
                interrupted = db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'running'").fetchone()[0]
                approvals = db.execute("SELECT COUNT(*) FROM approval_requests WHERE status = 'pending'").fetchone()[0]
                report["interrupted_tasks"] = interrupted
                report["pending_approvals"] = approvals
        except Exception:
            pass

        return report
