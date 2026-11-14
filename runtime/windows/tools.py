from typing import Any, Dict
from runtime.windows.discovery import WindowsDiscovery


class WindowsDiscoveryTools:
    """Registered handlers for read-only Windows discovery tools."""

    @staticmethod
    def host_info() -> Dict[str, Any]:
        return {
            "status": "success",
            "data": WindowsDiscovery.host_info(),
        }

    @staticmethod
    def cpu_memory() -> Dict[str, Any]:
        return {
            "status": "success",
            "data": WindowsDiscovery.cpu_memory(),
        }

    @staticmethod
    def disk_volumes() -> Dict[str, Any]:
        return WindowsDiscovery.disk_volumes()

    @staticmethod
    def running_processes(limit: int = 50) -> Dict[str, Any]:
        return WindowsDiscovery.running_processes(limit=limit)

    @staticmethod
    def network_info() -> Dict[str, Any]:
        return WindowsDiscovery.network_info()
