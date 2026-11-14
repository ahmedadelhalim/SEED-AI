from dataclasses import dataclass, field
from typing import Callable, Dict, Mapping, Optional, Tuple
import time


@dataclass(frozen=True)
class IntegrationError(RuntimeError):
    code: str
    message: str
    retryable: bool = False
    status_code: Optional[int] = None

    def __str__(self):
        return self.message


@dataclass
class Integration:
    name: str
    version: str
    adapter: object
    permission_scope: str
    enabled: bool = True
    auth_ref: Optional[str] = None
    last_health: Optional[Mapping[str, object]] = None
    failures: int = 0
    latency_ms: Tuple[float, ...] = field(default_factory=tuple)


class IntegrationRegistry:
    def __init__(self):
        self._integrations: Dict[str, Integration] = {}

    def register(self, integration: Integration):
        if not integration.name or integration.name in self._integrations:
            raise ValueError("Integration name is required and must be unique")
        if not integration.permission_scope:
            raise ValueError("Integration permission scope is required")
        self._integrations[integration.name] = integration

    def get(self, name: str) -> Integration:
        integration = self._integrations.get(name)
        if integration is None or not integration.enabled:
            raise IntegrationError("integration_unavailable", "Integration is unavailable")
        return integration

    def disable(self, name: str):
        self._integrations[name].enabled = False

    def enable(self, name: str):
        self._integrations[name].enabled = True

    def names(self):
        return tuple(self._integrations)

    def health(self, name: str):
        integration = self.get(name)
        started = time.perf_counter()
        try:
            result = integration.adapter.health()
            healthy = bool(result.get("healthy", True)) if isinstance(result, Mapping) else True
            integration.last_health = {"healthy": healthy, "result": result}
            return integration.last_health
        except IntegrationError:
            raise
        except Exception as error:
            integration.failures += 1
            raise IntegrationError("health_failed", "Integration health check failed", True) from error
        finally:
            integration.latency_ms = (*integration.latency_ms[-9:], round((time.perf_counter() - started) * 1000, 2))
