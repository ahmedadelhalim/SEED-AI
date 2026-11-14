import json
import urllib.request
from typing import Any, Dict, Optional, Tuple

from brain.model_types import ModelCapabilities, ModelRequest, ModelResponse, ToolCall
from brain.providers.base import (
    ModelProvider,
    ProviderError,
    RetryPolicy,
    Transport,
    parse_arguments,
    request_json,
)


class OllamaProvider(ModelProvider):
    name = "ollama"
    default_model = "qwen3:4b"

    def __init__(self, base_url: str = "http://127.0.0.1:11434",
                 default_model: str = "qwen3:4b", timeout_seconds: float = 180,
                 retry_policy: Optional[RetryPolicy] = None,
                 transport: Optional[Transport] = None):
        if timeout_seconds <= 0:
            raise ValueError("Ollama timeout_seconds must be positive")
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self.transport = transport

    def _request(self, path: str, body: Optional[Dict[str, Any]] = None,
                 timeout: Optional[float] = None) -> Dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method="POST" if data else "GET",
        )
        return request_json(
            request,
            timeout or self.timeout_seconds,
            self.retry_policy,
            self.transport,
        )

    def list_models(self) -> Tuple[str, ...]:
        response = self._request("/api/tags")
        models = response.get("models", [])
        return tuple(
            model["name"] for model in models
            if isinstance(model, dict) and isinstance(model.get("name"), str)
        )

    def capabilities(self, model: str) -> ModelCapabilities:
        response = self._request("/api/show", {"name": model})
        advertised = response.get("capabilities")
        features = tuple(item for item in advertised if isinstance(item, str)) \
            if isinstance(advertised, list) else ()
        tool_calling = "tools" in features if features else None
        return ModelCapabilities(
            tool_calling=tool_calling,
            features=features,
            source="ollama_api_show",
        )

    def chat(self, request: ModelRequest) -> ModelResponse:
        model = request.model or self.default_model
        payload = {
            "model": model,
            "messages": list(request.messages),
            "stream": False,
        }
        if request.tools:
            payload["tools"] = list(request.tools)
        options = {"num_predict": 256}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        payload["options"] = options
        if request.response_format is not None:
            payload["format"] = request.response_format

        response = self._request(
            "/api/chat", payload, request.timeout_seconds
        )
        message = response.get("message")
        if not isinstance(message, dict):
            raise ProviderError("invalid_response", "Ollama returned an invalid chat response")

        tool_calls = []
        for index, call in enumerate(message.get("tool_calls", [])):
            function = call.get("function", {}) if isinstance(call, dict) else {}
            name = function.get("name")
            if not isinstance(name, str):
                raise ProviderError("invalid_tool_call", "Ollama returned an invalid tool call")
            tool_calls.append(ToolCall(
                call_id=str(call.get("id", index)),
                name=name,
                arguments=parse_arguments(function.get("arguments", {})),
            ))

        raw_content = message.get("content") or ""
        if not raw_content and message.get("thinking"):
            raw_content = message.get("thinking")

        return ModelResponse(
            content=raw_content,
            provider=self.name,
            model=model,
            tool_calls=tuple(tool_calls),
            finish_reason=response.get("done_reason"),
            usage={
                key: response[key]
                for key in ("prompt_eval_count", "eval_count")
                if key in response
            },
        )