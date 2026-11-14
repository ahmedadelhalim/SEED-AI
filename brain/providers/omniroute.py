import json
import os
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple

from brain.model_types import ModelCapabilities, ModelRequest, ModelResponse, ToolCall
from brain.providers.base import (
    ModelProvider,
    ProviderError,
    RetryPolicy,
    Transport,
    parse_arguments,
    request_json,
)


def _environment_api_key() -> Optional[str]:
    return os.environ.get("OMNIROUTE_API_KEY")


class OmniRouteProvider(ModelProvider):
    name = "omniroute"
    default_model = ""

    def __init__(self, base_url: str = "http://127.0.0.1:20128",
                 default_model: str = "", timeout_seconds: float = 60,
                 api_key_provider: Optional[Callable[[], Optional[str]]] = None,
                 retry_policy: Optional[RetryPolicy] = None,
                 transport: Optional[Transport] = None):
        self.base_url = base_url.rstrip("/")
        self.api_base = self.base_url if self.base_url.endswith("/v1") \
            else self.base_url + "/v1"
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds
        self.api_key_provider = api_key_provider or _environment_api_key
        self.retry_policy = retry_policy or RetryPolicy()
        self.transport = transport

    def _request(self, path: str, body: Optional[Dict[str, Any]] = None,
                 timeout: Optional[float] = None) -> Dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"} if data else {}
        api_key = self.api_key_provider()
        if api_key:
            headers["Authorization"] = "Bearer " + api_key
        request = urllib.request.Request(
            self.api_base + path,
            data=data,
            headers=headers,
            method="POST" if data else "GET",
        )
        return request_json(
            request,
            timeout or self.timeout_seconds,
            self.retry_policy,
            self.transport,
        )

    def list_models(self) -> Tuple[str, ...]:
        response = self._request("/models")
        models = response.get("data", [])
        return tuple(
            model["id"] for model in models
            if isinstance(model, dict) and isinstance(model.get("id"), str)
        )

    def capabilities(self, model: str) -> ModelCapabilities:
        response = self._request("/models")
        models = response.get("data", [])
        item = next((entry for entry in models
                     if isinstance(entry, dict) and entry.get("id") == model), None)
        metadata = item if isinstance(item, dict) else {}
        advertised = metadata.get("capabilities")
        if isinstance(advertised, list):
            features = tuple(value for value in advertised if isinstance(value, str))
            tool_calling = "tools" in features if features else None
        else:
            features = ()
            tool_calling = metadata.get("tool_calling")
            if not isinstance(tool_calling, bool):
                tool_calling = metadata.get("supports_tools")
            if not isinstance(tool_calling, bool):
                tool_calling = None
        return ModelCapabilities(
            tool_calling=tool_calling,
            json_mode=metadata.get("json_mode")
            if isinstance(metadata.get("json_mode"), bool) else None,
            features=features,
            source="omniroute_model_metadata" if item else "unknown",
        )

    def chat(self, request: ModelRequest) -> ModelResponse:
        model = request.model or self.default_model
        if not model:
            raise ProviderError("model_required", "An OmniRoute model must be selected")
        payload = {
            "model": model,
            "messages": list(request.messages),
            "stream": False,
        }
        if request.tools:
            payload["tools"] = list(request.tools)
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        response = self._request(
            "/chat/completions", payload, request.timeout_seconds
        )
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderError("invalid_response", "OmniRoute returned an invalid chat response")
        choice = choices[0]
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ProviderError("invalid_response", "OmniRoute returned an invalid chat response")

        tool_calls = []
        for call in message.get("tool_calls", []):
            function = call.get("function", {}) if isinstance(call, dict) else {}
            name = function.get("name")
            if not isinstance(name, str):
                raise ProviderError("invalid_tool_call", "OmniRoute returned an invalid tool call")
            tool_calls.append(ToolCall(
                call_id=str(call.get("id", "")),
                name=name,
                arguments=parse_arguments(function.get("arguments", {})),
            ))

        usage = response.get("usage")
        return ModelResponse(
            content=message.get("content") or "",
            provider=self.name,
            model=model,
            tool_calls=tuple(tool_calls),
            finish_reason=choice.get("finish_reason"),
            usage=usage if isinstance(usage, dict) else {},
        )