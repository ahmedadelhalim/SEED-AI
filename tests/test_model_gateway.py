import json
import os
import urllib.error
import urllib.request
from unittest import TestCase
from unittest.mock import patch

from brain.gateway import ask_seedo
from brain.model_gateway import ModelGateway
from brain.model_types import ModelCapabilities, ModelRequest, ModelResponse
from brain.providers.base import (
    ModelCapabilityError,
    ModelProvider,
    ProviderError,
    RetryPolicy,
    request_json,
)
from brain.providers.ollama import OllamaProvider
from brain.providers.omniroute import OmniRouteProvider


class FakeProvider(ModelProvider):
    name = "fake"
    default_model = "fake-model"

    def __init__(self, tool_calling=None):
        self.tool_calling = tool_calling
        self.chat_requests = []

    def list_models(self):
        return (self.default_model,)

    def capabilities(self, model):
        return ModelCapabilities(
            tool_calling=self.tool_calling,
            source="test_metadata",
        )

    def chat(self, request):
        self.chat_requests.append(request)
        return ModelResponse("ok", self.name, request.model or self.default_model)


class DiscoveredProvider(FakeProvider):
    name = "discovered"
    default_model = ""

    def list_models(self):
        return ("catalog-model",)


class ModelGatewayTests(TestCase):
    def test_default_gateway_registers_local_providers_without_connecting(self):
        with patch.dict(os.environ, {
            "SEED_MODEL_PROVIDER": "",
            "OLLAMA_BASE_URL": "",
            "OLLAMA_MODEL": "",
            "OMNIROUTE_BASE_URL": "",
        }):
            gateway = ModelGateway.with_local_defaults()

        self.assertEqual(gateway.provider_names, ("ollama", "omniroute", "llama_embedded"))
        self.assertEqual(gateway.default_provider, "ollama")
        self.assertEqual(
            gateway.get_provider("ollama").default_model,
            "qwen3:4b",
        )
        self.assertEqual(
            gateway.get_provider("ollama").base_url,
            "http://127.0.0.1:11434",
        )
        self.assertEqual(
            gateway.get_provider("omniroute").api_base,
            "http://127.0.0.1:20128/v1",
        )
        self.assertEqual(
            gateway.get_provider("ollama").timeout_seconds,
            ModelGateway.DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        )

    def test_gateway_reads_configurable_omniroute_base_url(self):
        with patch.dict(
            os.environ,
            {"OMNIROUTE_BASE_URL": "http://127.0.0.1:22000/v1"},
        ):
            gateway = ModelGateway.with_local_defaults()

        self.assertEqual(
            gateway.get_provider("omniroute").api_base,
            "http://127.0.0.1:22000/v1",
        )

    def test_gateway_reads_configurable_ollama_timeout(self):
        with patch.dict(os.environ, {"OLLAMA_TIMEOUT_SECONDS": "240"}):
            gateway = ModelGateway.with_local_defaults()

        self.assertEqual(
            gateway.get_provider("ollama").timeout_seconds,
            240,
        )

    def test_gateway_allows_explicit_online_provider_opt_in(self):
        with patch.dict(os.environ, {
            "SEED_MODEL_PROVIDER": "omniroute",
            "OLLAMA_BASE_URL": "",
            "OLLAMA_MODEL": "",
            "OMNIROUTE_BASE_URL": "",
        }):
            gateway = ModelGateway.with_local_defaults()

        self.assertEqual(gateway.default_provider, "omniroute")

    def test_factory_argument_overrides_provider_environment(self):
        with patch.dict(os.environ, {"SEED_MODEL_PROVIDER": "omniroute"}):
            gateway = ModelGateway.with_local_defaults(default_provider="ollama")

        self.assertEqual(gateway.default_provider, "ollama")

    def test_gateway_rejects_unknown_default_provider(self):
        with self.assertRaises(ValueError):
            ModelGateway.with_local_defaults(default_provider="unknown")

    def test_ollama_chat_uses_native_endpoint_and_parses_tool_calls(self):
        captured = []

        def transport(request, timeout):
            captured.append((request, timeout))
            return json.dumps({
                "message": {
                    "content": "working",
                    "tool_calls": [{
                        "id": "call-1",
                        "function": {
                            "name": "workspace_list",
                            "arguments": '{"relative_path":"."}',
                        },
                    }],
                },
                "done_reason": "stop",
                "eval_count": 4,
            }).encode("utf-8")

        provider = OllamaProvider(transport=transport)
        response = provider.chat(ModelRequest(
            messages=({"role": "user", "content": "list"},),
            model="test-model",
            tools=({"type": "function"},),
            timeout_seconds=3,
        ))

        request, timeout = captured[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertEqual(timeout, 3)
        self.assertEqual(payload["model"], "test-model")
        self.assertIn("tools", payload)
        self.assertEqual(response.content, "working")
        self.assertEqual(response.tool_calls[0].name, "workspace_list")
        self.assertEqual(response.tool_calls[0].arguments, {"relative_path": "."})

    def test_ollama_capabilities_are_unknown_when_not_advertised(self):
        provider = OllamaProvider(
            transport=lambda _request, _timeout: b'{"details":{}}'
        )

        capabilities = provider.capabilities("model-without-metadata")

        self.assertIsNone(capabilities.tool_calling)

    def test_ollama_parses_multiple_tool_calls(self):
        provider = OllamaProvider(transport=lambda _request, _timeout: json.dumps({
            "message": {
                "content": "",
                "tool_calls": [
                    {"function": {"name": "workspace.list", "arguments": {"relative_path": "one"}}},
                    {"function": {"name": "workspace.list", "arguments": {"relative_path": "two"}}},
                ],
            },
        }).encode("utf-8"))

        response = provider.chat(ModelRequest(
            messages=({"role": "user", "content": "list both"},),
            tools=({"type": "function"},),
        ))

        self.assertEqual(len(response.tool_calls), 2)
        self.assertEqual(
            [call.arguments["relative_path"] for call in response.tool_calls],
            ["one", "two"],
        )

    def test_ollama_rejects_malformed_tool_arguments(self):
        provider = OllamaProvider(transport=lambda _request, _timeout: json.dumps({
            "message": {
                "content": "",
                "tool_calls": [{
                    "function": {
                        "name": "workspace.list",
                        "arguments": "{invalid",
                    },
                }],
            },
        }).encode("utf-8"))

        with self.assertRaises(ProviderError) as raised:
            provider.chat(ModelRequest(
                messages=({"role": "user", "content": "list"},),
                tools=({"type": "function"},),
            ))

        self.assertEqual(raised.exception.code, "invalid_tool_call")

    def test_omniroute_uses_openai_compatible_endpoint_and_secure_key_callback(self):
        captured = []

        def transport(request, timeout):
            captured.append((request, timeout))
            return json.dumps({
                "choices": [{
                    "message": {"content": "ready"},
                    "finish_reason": "stop",
                }],
                "usage": {"total_tokens": 5},
            }).encode("utf-8")

        provider = OmniRouteProvider(
            default_model="route-model",
            api_key_provider=lambda: "test-only-key",
            transport=transport,
        )
        response = provider.chat(ModelRequest(
            messages=({"role": "user", "content": "ping"},),
            timeout_seconds=4,
        ))

        request, timeout = captured[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(
            request.full_url,
            "http://127.0.0.1:20128/v1/chat/completions",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer test-only-key")
        self.assertEqual(timeout, 4)
        self.assertEqual(payload["model"], "route-model")
        self.assertEqual(response.content, "ready")
        self.assertEqual(response.usage["total_tokens"], 5)

    def test_omniroute_capabilities_use_advertised_model_metadata(self):
        provider = OmniRouteProvider(transport=lambda _request, _timeout: json.dumps({
            "data": [{"id": "route-model", "capabilities": ["tools", "json"]}],
        }).encode("utf-8"))

        capabilities = provider.capabilities("route-model")

        self.assertTrue(capabilities.tool_calling)
        self.assertEqual(capabilities.features, ("tools", "json"))

    def test_gateway_rejects_tools_when_capability_is_not_confirmed(self):
        provider = FakeProvider(tool_calling=None)
        gateway = ModelGateway((provider,), default_provider="fake")

        with self.assertRaises(ModelCapabilityError):
            gateway.complete(ModelRequest(
                messages=({"role": "user", "content": "use tool"},),
                tools=({"type": "function"},),
            ))

        self.assertEqual(provider.chat_requests, [])

    def test_gateway_selects_only_models_with_required_capability(self):
        provider = FakeProvider(tool_calling=True)
        gateway = ModelGateway((provider,))

        selection = gateway.select_model(require_tool_calling=True)

        self.assertEqual(selection.provider, "fake")
        self.assertEqual(selection.model, "fake-model")
        self.assertTrue(selection.capabilities.tool_calling)

    def test_gateway_prefers_configured_default_provider(self):
        fallback = FakeProvider(tool_calling=True)
        fallback.name = "fallback"
        preferred = FakeProvider(tool_calling=True)
        preferred.name = "preferred"
        gateway = ModelGateway(
            (fallback, preferred), default_provider="preferred"
        )

        selection = gateway.select_model()

        self.assertEqual(selection.provider, "preferred")

    def test_gateway_discovers_model_when_provider_has_no_default(self):
        provider = DiscoveredProvider(tool_calling=True)
        gateway = ModelGateway((provider,), default_provider="discovered")

        response = gateway.complete(ModelRequest(
            messages=({"role": "user", "content": "hello"},),
        ))

        self.assertEqual(response.model, "catalog-model")
        self.assertEqual(provider.chat_requests[0].model, "catalog-model")

    def test_gateway_returns_normalized_error_after_bounded_retries(self):
        attempts = []

        def unavailable(_request, _timeout):
            attempts.append(True)
            raise urllib.error.URLError("offline")

        with self.assertRaises(ProviderError) as raised:
            request_json(
                urllib.request.Request("http://localhost/test"),
                1,
                RetryPolicy(max_attempts=2, base_delay=0, max_delay=0),
                unavailable,
            )

        self.assertEqual(raised.exception.code, "connection")
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(len(attempts), 2)

    def test_legacy_ollama_helper_uses_gateway_and_returns_content(self):
        class FakeGateway:
            def complete(self, request):
                self.request = request
                return ModelResponse("legacy response", "ollama", "qwen3:4b")

        fake_gateway = FakeGateway()
        with patch("brain.gateway.ModelGateway.with_local_defaults", return_value=fake_gateway):
            result = ask_seedo("legacy prompt")

        self.assertEqual(result, "legacy response")
        self.assertEqual(fake_gateway.request.messages[0]["content"], "legacy prompt")
        self.assertEqual(fake_gateway.request.provider, "ollama")


if __name__ == "__main__":
    import unittest

    unittest.main()