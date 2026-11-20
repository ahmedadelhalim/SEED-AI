from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class ModelRequest:
    messages: Tuple[Mapping[str, Any], ...]
    model: Optional[str] = None
    tools: Tuple[Mapping[str, Any], ...] = ()
    temperature: Optional[float] = None
    timeout_seconds: Optional[float] = None
    provider: Optional[str] = None
    response_format: Optional[Mapping[str, Any]] = None
    cancellation_token: Optional[Any] = None

    def __post_init__(self):
        if not self.messages:
            raise ValueError("At least one message is required")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class ModelResponse:
    content: str
    provider: str
    model: str
    tool_calls: Tuple[ToolCall, ...] = ()
    finish_reason: Optional[str] = None
    usage: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelCapabilities:
    tool_calling: Optional[bool] = None
    json_mode: Optional[bool] = None
    streaming: Optional[bool] = None
    features: Tuple[str, ...] = ()
    source: str = "unknown"


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    healthy: bool
    checked_at: str
    model_count: int = 0
    error_code: Optional[str] = None


@dataclass(frozen=True)
class ModelSelection:
    provider: str
    model: str
    capabilities: ModelCapabilities