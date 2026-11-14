import json
import socket
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from brain.model_types import (
    ModelCapabilities,
    ModelRequest,
    ModelResponse,
    ProviderHealth,
)


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False,
                 status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code


class ModelCapabilityError(ProviderError):
    def __init__(self, provider: str, model: str):
        super().__init__(
            "tool_calling_unsupported",
            "Tool calling is not confirmed for the selected model",
        )
        self.provider = provider
        self.model = model


class RetryPolicy:
    def __init__(self, max_attempts: int = 2, base_delay: float = 0.15,
                 max_delay: float = 1.0):
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if base_delay < 0 or max_delay < 0:
            raise ValueError("Retry delays cannot be negative")
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay


Transport = Callable[[urllib.request.Request, float], bytes]


def request_json(request: urllib.request.Request, timeout: float,
                 retry_policy: RetryPolicy,
                 transport: Optional[Transport] = None) -> Dict[str, Any]:
    for attempt in range(retry_policy.max_attempts):
        try:
            if transport is not None:
                response_body = transport(request, timeout)
            else:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    response_body = response.read()
            result = json.loads(response_body.decode("utf-8"))
            if not isinstance(result, dict):
                raise ProviderError("invalid_response", "Provider returned invalid JSON")
            return result
        except urllib.error.HTTPError as error:
            status_code = error.code
            if status_code in (401, 403):
                provider_error = ProviderError(
                    "authentication", "Provider authentication failed", False,
                    status_code,
                )
            elif status_code == 429:
                provider_error = ProviderError(
                    "rate_limited", "Provider rate limit reached", True, status_code
                )
            else:
                retryable = status_code == 408 or status_code >= 500
                provider_error = ProviderError(
                    "provider_unavailable" if retryable else "request_rejected",
                    "Provider request failed", retryable, status_code,
                )
        except urllib.error.URLError as error:
            timed_out = isinstance(error.reason, (TimeoutError, socket.timeout))
            provider_error = ProviderError(
                "timeout" if timed_out else "connection",
                "Provider request timed out" if timed_out else "Provider connection failed",
                True,
            )
        except (TimeoutError, socket.timeout):
            provider_error = ProviderError(
                "timeout", "Provider request timed out", True
            )
        except (UnicodeDecodeError, ValueError):
            raise ProviderError("invalid_response", "Provider returned invalid JSON")
        except ProviderError as error:
            provider_error = error

        if not provider_error.retryable or attempt + 1 >= retry_policy.max_attempts:
            raise provider_error
        delay = min(
            retry_policy.base_delay * (2 ** attempt), retry_policy.max_delay
        )
        if delay:
            time.sleep(delay)

    raise ProviderError("request_failed", "Provider request failed")


class ModelProvider(ABC):
    name = ""
    default_model = ""

    @abstractmethod
    def list_models(self) -> Tuple[str, ...]:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self, model: str) -> ModelCapabilities:
        raise NotImplementedError

    @abstractmethod
    def chat(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    def health_check(self) -> ProviderHealth:
        checked_at = datetime.now(timezone.utc).isoformat()
        try:
            models = self.list_models()
        except ProviderError as error:
            return ProviderHealth(
                provider=self.name,
                healthy=False,
                checked_at=checked_at,
                error_code=error.code,
            )
        return ProviderHealth(
            provider=self.name,
            healthy=True,
            checked_at=checked_at,
            model_count=len(models),
        )


def parse_arguments(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            arguments = json.loads(value)
        except ValueError as error:
            raise ProviderError(
                "invalid_tool_call", "Provider returned invalid tool arguments"
            ) from error
        if isinstance(arguments, dict):
            return arguments
    raise ProviderError("invalid_tool_call", "Provider returned invalid tool arguments")