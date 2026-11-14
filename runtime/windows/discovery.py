import os
import platform
import psutil
import shutil
import socket
from typing import Any, Dict, List, Optional


class WindowsDiscovery:
    """Read-only Windows system discovery and diagnostic tools."""

    @staticmethod
    def host_info() -> Dict[str, Any]:
        return {
            "node": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "username": os.getlogin() if hasattr(os, "getlogin") else "unknown",
        }

    @staticmethod
    def cpu_memory() -> Dict[str, Any]:
        virtual_mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "physical_cores": psutil.cpu_count(logical=False),
            "total_logical_cpus": psutil.cpu_count(logical=True),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            "memory": {
                "total_bytes": virtual_mem.total,
                "available_bytes": virtual_mem.available,
                "used_bytes": virtual_mem.used,
                "percent": virtual_mem.percent,
            },
            "swap": {
                "total_bytes": swap.total,
                "used_bytes": swap.used,
                "percent": swap.percent,
            },
        }

    @staticmethod
    def disk_volumes() -> Dict[str, Any]:
        partitions = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "opts": part.opts,
                    "total_bytes": usage.total,
                    "used_bytes": usage.used,
                    "free_bytes": usage.free,
                    "percent": usage.percent,
                })
            except (PermissionError, OSError):
                continue
        return {
            "status": "success",
            "partitions": partitions,
        }

    @staticmethod
    def running_processes(limit: int = 50) -> Dict[str, Any]:
        procs = []
        for p in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
            try:
                info = p.info
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "username": info["username"],
                    "cpu_percent": info.get("cpu_percent", 0.0),
                    "memory_percent": info.get("memory_percent", 0.0),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            if len(procs) >= limit:
                break
        return {
            "status": "success",
            "count": len(procs),
            "processes": procs,
        }

    @staticmethod
    def network_info() -> Dict[str, Any]:
        interfaces = {}
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        for interface_name, entries in addrs.items():
            if_stats = stats.get(interface_name)
            interfaces[interface_name] = {
                "is_up": if_stats.isup if if_stats else None,
                "speed_mbps": if_stats.speed if if_stats else None,
                "addresses": [
                    {
                        "family": str(entry.family),
                        "address": entry.address,
                        "netmask": entry.netmask,
                    }
                    for entry in entries
                ],
            }

        connections = []
        try:
            for conn in psutil.net_connections(kind="inet")[:50]:
                connections.append({
                    "fd": conn.fd,
                    "family": str(conn.family),
                    "type": str(conn.type),
                    "local_address": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                    "remote_address": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                    "status": conn.status,
                })
        except (psutil.AccessDenied, psutil.ZombieProcess):
            pass

        return {
            "status": "success",
            "hostname": socket.gethostname(),
            "interfaces": interfaces,
            "active_connections_sample": connections,
        }
