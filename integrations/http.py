import json
import time
import urllib.error
import urllib.request
from typing import Any, Mapping, Optional

from integrations.registry import IntegrationError


class HttpIntegration:
    def __init__(self, base_url: str, timeout_seconds: float = 10, retries: int = 1,
                 opener=urllib.request.urlopen):
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("HTTP integration requires an HTTP(S) base URL")
        if timeout_seconds <= 0 or retries < 0:
            raise ValueError("Invalid HTTP integration limits")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.opener = opener

    def health(self):
        return {"healthy": True, "base_url": self.base_url}

    def request(self, method: str, path: str, body: Optional[Mapping[str, Any]] = None):
        if not path.startswith("/") or ".." in path.split("/"):
            raise IntegrationError("invalid_path", "Integration path is invalid")
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method=method.upper(),
        )
        last_error = None
        for attempt in range(self.retries + 1):
            started = time.perf_counter()
            try:
                with self.opener(request, timeout=self.timeout_seconds) as response:
                    raw = response.read()
                    value = json.loads(raw.decode("utf-8")) if raw else None
                    return {"status_code": response.status, "body": value,
                            "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
            except urllib.error.HTTPError as error:
                retryable = error.code == 429 or error.code >= 500
                last_error = IntegrationError("http_error", "HTTP integration request failed", retryable, error.code)
            except (urllib.error.URLError, TimeoutError):
                last_error = IntegrationError("connection", "HTTP integration connection failed", True)
            if not last_error.retryable or attempt >= self.retries:
                raise last_error
        raise last_error


def register_http_integration(name, integration, tool_registry, permission_engine):
    from core.tool_registry import ToolDefinition

    tool_name = "integration." + name + ".request"

    def handler(method="GET", path="/", body=None):
        if method.upper() != "GET":
            raise ValueError("Read-only HTTP integration accepts GET only")
        return integration.request("GET", path, body)

    tool_registry.register(ToolDefinition(
        name=tool_name,
        description="Perform a governed read-only HTTP integration request.",
        handler=handler,
        parameters={
            "type": "object",
            "properties": {
                "method": {"type": "string"},
                "path": {"type": "string"},
                "body": {"type": "object"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        action="read",
        scope="network",
        parallel_safe=False,
        retry_safe=True,
    ))
    permission_engine.register_policy(
        tool_name, "read", "network", allowed=True, approval=False,
        skill_id="integration:" + name, artifact_digest="builtin",
    )
    return tool_name
