import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Optional


@dataclass(frozen=True)
class ServiceHealth:
    name: str
    kind: str
    status: str
    checked_at: Optional[str] = None
    error_code: Optional[str] = None


class ServiceRegistry:
    def __init__(self):
        self._checks = {}  # type: Dict[str, tuple]
        self._health = {}  # type: Dict[str, ServiceHealth]
        self._lock = threading.Lock()

    def __contains__(self, name: str):
        with self._lock:
            return name in self._checks

    def register(self, name: str, kind: str,
                 health_check: Optional[Callable[[], bool]] = None):
        if not name or not kind:
            raise ValueError("Service name and kind are required")
        with self._lock:
            if name in self._checks:
                raise ValueError("Service is already registered")
            self._checks[name] = (kind, health_check)
            self._health[name] = ServiceHealth(
                name=name,
                kind=kind,
                status="unverified" if health_check is not None else "registered",
            )

    def check(self, name: str) -> ServiceHealth:
        with self._lock:
            if name not in self._checks:
                raise KeyError("Service is not registered")
            kind, health_check = self._checks[name]
        if health_check is None:
            return self._health[name]
        checked_at = datetime.now(timezone.utc).isoformat()
        try:
            healthy = bool(health_check())
            status = "healthy" if healthy else "unhealthy"
            error_code = None
        except Exception as error:
            status = "unhealthy"
            error_code = type(error).__name__
        result = ServiceHealth(name, kind, status, checked_at, error_code)
        with self._lock:
            self._health[name] = result
        return result

    def snapshot(self, refresh=False):
        with self._lock:
            names = tuple(self._checks)
            current = dict(self._health)
        if refresh:
            return {name: self.check(name) for name in names}
        return current