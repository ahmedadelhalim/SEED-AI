"""SEED Real Local Inference Provider - llama-cpp-python backend

This provider uses the actual llama-cpp-python library to load the Qwen3:4B
GGUF model and perform genuine local inference. It replaces the deterministic
template-only EmbeddedLlamaProvider with real token generation.

Key requirements enforced:
- Actual model loading (not just GGUF header validation)
- Real token generation
- Streaming support where feasible
- Configurable context and generation parameters
- Proper cancellation and timeout handling
- Explicit model lifecycle management
- Resource cleanup and error handling
- Accurate health and readiness reporting
"""

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Tuple

from brain.model_types import ModelCapabilities, ModelRequest, ModelResponse, ToolCall
from brain.providers.base import ModelCapabilityError, ModelProvider, ProviderError, ProviderHealth


class RealLlamaProvider(ModelProvider):
    """Real local inference using llama-cpp-python with genuine token generation."""

    name = "llama_real"
    default_model = "qwen3:4b"

    def __init__(self, model_path: Optional[str] = None,
                 default_model: str = "qwen3:4b",
                 timeout_seconds: float = 180,
                 n_ctx: int = 8192,
                 n_threads: int = 4,
                 n_gpu_layers: int = 0,
                 temperature: float = 0.7,
                 max_tokens: int = 64,
                 thinking_mode: bool = False):
        self.model_path = model_path or os.environ.get(
            "SEED_MODEL_PATH",
            "D:/SEED-AI/models/qwen3-4b.gguf"
        )
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.n_gpu_layers = n_gpu_layers
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.thinking_mode = thinking_mode

        self._loaded = False
        self._model = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._cancel_event = threading.Event()

    def load_model(self) -> bool:
        """Actually load the GGUF model into memory and initialize inference."""
        if self._loaded:
            return True

        with self._load_lock:
            if self._loaded:
                return True

            if not self._model:
                from llama_cpp import Llama
                self._model = Llama(
                    model_path=self.model_path,
                    n_ctx=self.n_ctx,
                    n_threads=self.n_threads,
                    n_gpu_layers=self.n_gpu_layers,
                    n_batch=128,
                    verbose=False,
                )

            self._loaded = True
            return True

    def unload_model(self):
        """Release model resources safely by acquiring both load and inference locks."""
        with self._load_lock:
            with self._inference_lock:
                if self._model is not None:
                    try:
                        del self._model
                    except Exception:
                        pass
                    self._model = None
                self._loaded = False
                import gc
                gc.collect()

    def is_ready(self) -> bool:
        """Return True if model is loaded and ready for inference."""
        return self._loaded and self._model is not None

    def tokenize(self, text: str) -> int:
        """Count tokens using the already-loaded inference model's tokenizer.

        Returns the number of tokens in *text*.  If the model is not yet
        loaded, returns a conservative heuristic estimate (2 chars/token)
        so that no model is loaded solely for token counting.

        Thread-safe: acquires _inference_lock during tokenization.
        """
        if not text:
            return 0
        if self._model is not None:
            with self._inference_lock:
                try:
                    return len(self._model.tokenize(text.encode("utf-8")))
                except Exception:
                    pass
        # Fallback: conservative 2 chars/token for Arabic/CJK safety
        return max(1, len(text) // 2)

    def tokenize_exact(self, text: str) -> Optional[int]:
        """Return exact token count if model is loaded, else None."""
        if not text or self._model is None:
            return None
        with self._inference_lock:
            try:
                return len(self._model.tokenize(text.encode("utf-8")))
            except Exception:
                return None

    def count_chat_tokens(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> int:
        """Count tokens using the exact same formatting as inference.

        Uses the GGUF's embedded Jinja chat template rendered via
        Jinja2ChatFormatter, then tokenized with add_bos=True, special=True
        — matching the path used by ``create_chat_completion`` internally.
        Tool definitions are included in the template rendering (same as
        inference when ``tools`` is passed to create_chat_completion).

        Never silently falls back to raw-text counting.  If the template is
        missing, unsupported, or rendering fails, raises ProviderError.

        Args:
            messages: OpenAI-style message list (role, content, ...).
            tools: Optional list of tool definitions (OpenAI format) to
                   include in template rendering.

        Returns:
            Exact token count matching inference ``usage.prompt_tokens``.
        """
        if not self.load_model():
            raise ProviderError(
                "model_load_failed",
                "Cannot count chat tokens: model not loaded",
            )

        # Normalize messages
        normalized: List[Dict[str, Any]] = []
        for msg in (messages or []):
            if not isinstance(msg, Mapping):
                continue
            role = msg.get("role", "user")
            content = msg.get("content", "")
            entry: Dict[str, Any] = {"role": role, "content": content}
            if "tool_call_id" in msg:
                entry["tool_call_id"] = msg["tool_call_id"]
            if "name" in msg:
                entry["name"] = msg["name"]
            if "tool_calls" in msg:
                entry["tool_calls"] = msg["tool_calls"]
            normalized.append(entry)
        if not normalized:
            normalized = [{"role": "user", "content": ""}]

        try:
            from llama_cpp.llama_chat_format import Jinja2ChatFormatter

            template = self._model.metadata.get("tokenizer.chat_template")
            if not template:
                raise ProviderError(
                    "no_chat_template",
                    "GGUF metadata does not contain tokenizer.chat_template",
                )

            # Resolve eos/bos token strings from metadata
            eos_token_id = self._model.metadata.get("tokenizer.ggml.eos_token_id")
            bos_token_id = self._model.metadata.get("tokenizer.ggml.bos_token_id")
            eos_token = ""
            bos_token = ""
            if eos_token_id is not None:
                try:
                    eos_token = self._model.detokenize([int(eos_token_id)])
                    if isinstance(eos_token, bytes):
                        eos_token = eos_token.decode("utf-8", errors="replace")
                except Exception:
                    eos_token = ""
            if bos_token_id is not None:
                try:
                    bos_token = self._model.detokenize([int(bos_token_id)])
                    if isinstance(bos_token, bytes):
                        bos_token = bos_token.decode("utf-8", errors="replace")
                except Exception:
                    bos_token = ""

            formatter = Jinja2ChatFormatter(
                template=template,
                eos_token=eos_token,
                bos_token=bos_token,
                add_generation_prompt=True,
            )
            result = formatter(messages=normalized, tools=tools)
            prompt_text = result.prompt

            with self._inference_lock:
                token_ids = self._model.tokenize(
                    prompt_text.encode("utf-8"),
                    add_bos=not result.added_special,
                    special=True,
                )
            return len(token_ids)

        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                "chat_token_count_failed",
                f"Chat template token counting failed: {exc}",
            ) from exc

    def list_models(self) -> Tuple[str, ...]:
        if not self.load_model():
            return ()
        return (self.default_model,)

    def capabilities(self, model: str) -> ModelCapabilities:
        return ModelCapabilities(
            tool_calling=True,
            json_mode=True,
            streaming=True,
            features=("completion", "tools", "embedded", "real_inference", "llama_cpp"),
            source="llama_cpp_native",
        )

    def _build_messages(self, request: ModelRequest) -> List[Dict[str, Any]]:
        """Build an OpenAI-style message list for llama-cpp's chat template.

        We deliberately pass messages through to ``create_chat_completion`` so
        that the GGUF's embedded Jinja chat template (verified present in the
        Qwen3 artifact) is applied. Raw string concatenation caused the model to
        continue the transcript instead of answering the user.
        """
        messages: List[Dict[str, Any]] = []
        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            entry: Dict[str, Any] = {"role": role, "content": content}
            tool_call_id = msg.get("tool_call_id")
            if tool_call_id:
                entry["tool_call_id"] = tool_call_id
            name = msg.get("name")
            if name:
                entry["name"] = name
            messages.append(entry)
        if not messages:
            messages = [{"role": "user", "content": ""}]
        return messages

    def _stop_sequences(self, request: ModelRequest) -> List[str]:
        return ["Human:", "Assistant:", "user:", "system:"]

    def _resolve_timeout(self, request: ModelRequest) -> float:
        if request.timeout_seconds is not None:
            return float(request.timeout_seconds)
        return float(self.timeout_seconds)

    def _extract_tool_calls(self, message: Mapping[str, Any]) -> Tuple[ToolCall, ...]:
        calls: List[ToolCall] = []
        raw = message.get("tool_calls") or ()
        for index, call in enumerate(raw):
            if not isinstance(call, Mapping):
                continue
            function = call.get("function", {})
            if not isinstance(function, Mapping):
                continue
            name = function.get("name", "")
            if not name:
                continue
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except (ValueError, TypeError):
                    arguments = {}
            if not isinstance(arguments, Mapping):
                arguments = {}
            calls.append(ToolCall(
                call_id=str(call.get("id") or f"llama_real_call_{index}"),
                name=str(name),
                arguments=arguments,
            ))
        return tuple(calls)

    def chat(self, request: ModelRequest) -> ModelResponse:
        """Perform real token generation using the GGUF chat template."""
        model = request.model or self.default_model

        if not self.load_model():
            raise ProviderError(
                "model_load_failed",
                "Real inference model could not be loaded (llama-cpp-python backend unavailable)",
            )

        timeout = self._resolve_timeout(request)
        messages = self._build_messages(request)
        temperature = (
            request.temperature if request.temperature is not None
            else self.temperature
        )

        # Per-request max_tokens override with safety bounds
        request_max = getattr(request, "max_tokens", None)
        effective_max = request_max if request_max is not None else self.max_tokens
        effective_max = max(1, min(effective_max, 4096))  # safety bounds: 1-4096

        kwargs: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": effective_max,
            "temperature": temperature,
            "stop": self._stop_sequences(request),
        }
        response_format = getattr(request, "response_format", None)
        if isinstance(response_format, Mapping) and response_format.get("type") == "json":
            kwargs["response_format"] = {"type": "json_object"}

        deadline = time.monotonic() + timeout
        cancel_token = getattr(request, "cancellation_token", None) or threading.Event()
        if hasattr(cancel_token, "clear"):
            try:
                cancel_token.clear()
            except Exception:
                pass

        try:
            with self._inference_lock:
                if self._model is None or not self._loaded:
                    if not self.load_model() or self._model is None:
                        raise ProviderError("model_not_loaded", "Model not loaded")
                if hasattr(cancel_token, "is_set") and cancel_token.is_set():
                    raise ProviderError("cancelled", "Request was cancelled before inference started")
                result = self._model.create_chat_completion(**kwargs)
        except Exception as error:  # noqa: BLE001 - normalize backend failures
            raise ProviderError(
                "inference_failed",
                f"Real model inference failed: {error}",
            ) from error

        if time.monotonic() > deadline:
            raise ProviderError(
                "timeout",
                f"Inference exceeded timeout of {timeout:.1f}s",
                retryable=True,
            )

        choices = (result or {}).get("choices") or []
        if not choices:
            raise ProviderError(
                "invalid_response",
                "Real model inference produced no choices",
            )

        message = choices[0].get("message") or {}
        content = message.get("content")
        if content is None:
            content = ""
        if not isinstance(content, str):
            content = str(content)

        # Clean up Qwen3 thinking tags or reasoning residue if present
        if content:
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
            content = content.strip()

        usage_raw = (result or {}).get("usage") or {}
        usage = {
            "prompt_tokens": int(usage_raw.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage_raw.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage_raw.get("total_tokens", 0) or 0),
            "backend": "llama_cpp",
        }
        if not usage["prompt_tokens"] and not usage["completion_tokens"]:
            usage = {
                "prompt_eval_count": len(str(messages).split()),
                "eval_count": len(content.split()),
                "backend": "llama_cpp",
            }

        return ModelResponse(
            content=content.strip(),
            provider=self.name,
            model=model,
            tool_calls=self._extract_tool_calls(message),
            finish_reason=choices[0].get("finish_reason") or "stop",
            usage=usage,
        )

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

    def cancel(self, token: Optional[Any] = None) -> None:
        """Signal cooperative cancellation for a specific request token or globally."""
        if token is not None and hasattr(token, "set"):
            token.set()
        else:
            self._cancel_event.set()

    def chat_stream(self, request: ModelRequest,
                    callback: Callable[[str], None]) -> Iterator[str]:
        """Stream tokens from the model in real-time under inference lock protection with request-scoped cancellation and chunk-level timeout."""
        model = request.model or self.default_model

        if not self.load_model():
            raise ProviderError("model_load_failed", "Real inference model could not be loaded")

        messages = self._build_messages(request)

        timeout = self._resolve_timeout(request)
        temperature = (
            request.temperature if request.temperature is not None
            else self.temperature
        )

        kwargs: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "stop": self._stop_sequences(request),
            "stream": True,
        }
        response_format = getattr(request, "response_format", None)
        if isinstance(response_format, Mapping) and response_format.get("type") == "json":
            kwargs["response_format"] = {"type": "json_object"}

        accumulated = ""

        def _emit(token: str):
            nonlocal accumulated
            accumulated += token
            callback(token)

        cancel_token = getattr(request, "cancellation_token", None) or self._cancel_event
        if hasattr(cancel_token, "clear"):
            try:
                cancel_token.clear()
            except Exception:
                pass

        deadline = time.monotonic() + timeout
        result_generator = None

        try:
            with self._inference_lock:
                if self._model is None or not self._loaded:
                    if not self.load_model() or self._model is None:
                        raise ProviderError("model_not_loaded", "Model not loaded")
                try:
                    result_generator = self._model.create_chat_completion(**kwargs)  # type: ignore[attr-defined]
                except Exception as error:  # noqa: BLE001 - normalize backend failures
                    raise ProviderError(
                        "inference_failed",
                        f"Real model inference failed: {error}",
                    ) from error

                # Consume the stream generator under lock protection with chunk-level timeout and cancellation checks
                for chunk in result_generator:
                    if hasattr(cancel_token, "is_set") and cancel_token.is_set():
                        break
                    if time.monotonic() > deadline:
                        raise ProviderError(
                            "timeout",
                            f"Streaming generation exceeded timeout of {timeout:.1f}s",
                            retryable=True,
                        )
                    # chunk is typically a dict with 'choices' key
                    choices = chunk.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content", "")
                        if content:
                            _emit(content)
                    # Also check for content in the chunk itself
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        msg = chunk["choices"][0].get("message", {})
                        if msg.get("content"):
                            _emit(msg["content"])
        except ProviderError:
            raise
        except Exception as error:
            is_cancelled = False
            if hasattr(cancel_token, "is_set") and cancel_token.is_set():
                is_cancelled = True
            if not is_cancelled:
                try:
                    with self._inference_lock:
                        result = self._model.create_chat_completion(
                            messages=messages,
                            max_tokens=self.max_tokens,
                            temperature=temperature,
                            stop=self._stop_sequences(request),
                            stream=False,
                        )
                        choices = (result or {}).get("choices") or []
                        if choices:
                            message = choices[0].get("message") or {}
                            content = message.get("content") or ""
                            if content:
                                _emit(content)
                except Exception as fallback_error:
                    raise ProviderError(
                        "inference_failed",
                        f"Real model inference failed: {fallback_error}",
                    ) from fallback_error
            else:
                pass
        finally:
            if result_generator is not None:
                try:
                    if hasattr(result_generator, "close"):
                        result_generator.close()
                except Exception:
                    pass

        yield accumulated