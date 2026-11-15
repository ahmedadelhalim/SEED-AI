import os
from typing import Dict, Iterable, Optional, Tuple

from brain.model_types import (
    ModelCapabilities,
    ModelRequest,
    ModelResponse,
    ModelSelection,
)
from brain.providers.base import ModelCapabilityError, ModelProvider, ProviderError


class ModelGateway:
    DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
    DEFAULT_OLLAMA_MODEL = "qwen3:4b"
    DEFAULT_OLLAMA_TIMEOUT_SECONDS = 180.0
    DEFAULT_OMNIROUTE_BASE_URL = "http://127.0.0.1:20128/v1"
    SUPPORTED_PROVIDERS = ("ollama", "omniroute", "llama_embedded", "llama_real")

    def __init__(self, providers: Iterable[ModelProvider] = (),
                 default_provider: Optional[str] = None):
        self._providers = {}  # type: Dict[str, ModelProvider]
        self._capabilities = {}  # type: Dict[Tuple[str, str], ModelCapabilities]
        for provider in providers:
            self.register(provider)
        self.default_provider = default_provider

    @classmethod
    def with_local_defaults(cls, ollama_base_url: Optional[str] = None,
                            omniroute_base_url: Optional[str] = None,
                            default_provider: Optional[str] = None):
        from brain.providers.omniroute import OmniRouteProvider
        from brain.providers.ollama import OllamaProvider
        from brain.providers.llama_embedded import EmbeddedLlamaProvider
        from brain.providers.llama_real import RealLlamaProvider

        configured_ollama_url = (
            ollama_base_url
            or os.environ.get("OLLAMA_BASE_URL")
            or cls.DEFAULT_OLLAMA_BASE_URL
        )
        configured_omniroute_url = (
            omniroute_base_url
            or os.environ.get("OMNIROUTE_BASE_URL")
            or cls.DEFAULT_OMNIROUTE_BASE_URL
        )
        configured_default = (
            default_provider
            or os.environ.get("SEED_MODEL_PROVIDER")
            or "ollama"
        ).strip().lower()
        if configured_default not in cls.SUPPORTED_PROVIDERS:
            raise ValueError("SEED_MODEL_PROVIDER must be ollama, omniroute, llama_embedded, or llama_real")

        return cls(
            (OllamaProvider(
                base_url=configured_ollama_url,
                default_model=os.environ.get("OLLAMA_MODEL") or cls.DEFAULT_OLLAMA_MODEL,
                timeout_seconds=float(
                    os.environ.get("OLLAMA_TIMEOUT_SECONDS")
                    or cls.DEFAULT_OLLAMA_TIMEOUT_SECONDS
                ),
            ),
             OmniRouteProvider(base_url=configured_omniroute_url),
             EmbeddedLlamaProvider(),
             RealLlamaProvider()),
            default_provider=configured_default,
        )

    @property
    def provider_names(self):
        return tuple(self._providers.keys())

    def register(self, provider: ModelProvider):
        if not provider.name:
            raise ValueError("Provider name is required")
        if provider.name in self._providers:
            raise ValueError("Provider is already registered")
        self._providers[provider.name] = provider

    def get_provider(self, name: str) -> ModelProvider:
        try:
            return self._providers[name]
        except KeyError as error:
            raise ProviderError("unknown_provider", "Selected model provider is not registered") from error

    def discover_capabilities(self, provider: str, model: str) -> ModelCapabilities:
        key = (provider, model)
        if key not in self._capabilities:
            self._capabilities[key] = self.get_provider(provider).capabilities(model)
        return self._capabilities[key]

    def select_model(self, model: Optional[str] = None,
                     provider_name: Optional[str] = None,
                     require_tool_calling: bool = False) -> ModelSelection:
        if provider_name is not None:
            provider_names = (provider_name,)
        else:
            provider_names = tuple(
                name for name in (self.default_provider, *self._providers.keys())
                if name in self._providers
            )

        for name in provider_names:
            provider = self.get_provider(name)
            models = (model,) if model else provider.list_models()
            for candidate in models:
                capabilities = self.discover_capabilities(name, candidate)
                if require_tool_calling and capabilities.tool_calling is not True:
                    continue
                return ModelSelection(name, candidate, capabilities)
        raise ProviderError(
            "no_compatible_model", "No available model satisfies the requested capabilities"
        )

    def complete(self, request: ModelRequest,
                 provider_name: Optional[str] = None) -> ModelResponse:
        name = provider_name or request.provider or self.default_provider
        if name is None:
            raise ProviderError("provider_required", "A model provider must be selected")
        provider = self.get_provider(name)
        model = request.model or provider.default_model
        if not model:
            selection = self.select_model(
                provider_name=name,
                require_tool_calling=bool(request.tools),
            )
            model = selection.model
        if request.tools:
            capabilities = self.discover_capabilities(name, model)
            if capabilities.tool_calling is not True:
                raise ModelCapabilityError(name, model)
        if request.model == model:
            return provider.chat(request)
        routed_request = ModelRequest(
            messages=request.messages,
            model=model,
            tools=request.tools,
            temperature=request.temperature,
            timeout_seconds=request.timeout_seconds,
            provider=name,
            response_format=request.response_format,
        )
        return provider.chat(routed_request)

    def health(self):
        return {
            name: provider.health_check()
            for name, provider in self._providers.items()
        }