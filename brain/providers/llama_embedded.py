"""
SEED Embedded Native In-Process GGUF Runtime Provider

Validates GGUF model assets in-process and executes genuine local inference
using llama-cpp-python. Provides deterministic tool-call routing for
recognized system/file/tool commands, and real token generation for all
other natural-language prompts.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from brain.model_types import ModelCapabilities, ModelRequest, ModelResponse, ToolCall
from brain.providers.base import ModelProvider, ProviderError

# Real inference backend (replaces deterministic templates)
from brain.providers.llama_real import RealLlamaProvider


class EmbeddedLlamaProvider(ModelProvider):
    """Embedded GGUF runtime provider with real Qwen inference."""

    name = "llama_embedded"
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
        self._real_backend: Optional[RealLlamaProvider] = None

    def _ensure_backend(self) -> RealLlamaProvider:
        if self._real_backend is None:
            self._real_backend = RealLlamaProvider(
                model_path=self.model_path,
                default_model=self.default_model,
                timeout_seconds=self.timeout_seconds,
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                n_gpu_layers=self.n_gpu_layers,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                thinking_mode=self.thinking_mode,
            )
        return self._real_backend

    def load_model(self) -> bool:
        """Actually load the GGUF model into memory and initialize inference.

        Returns True only once llama-cpp-python has successfully initialized
        the model weights. Never reports ``loaded=True`` based solely on a
        GGUF header check.
        """
        if self._loaded:
            return True
        try:
            backend = self._ensure_backend()
            if backend.load_model():
                self._loaded = True
                return True
        except Exception:
            self._loaded = False
            return False
        return False

    def unload_model(self):
        """Release model resources."""
        if self._real_backend is not None:
            try:
                self._real_backend.unload_model()
            except Exception:
                pass
        self._loaded = False
        self._real_backend = None

    def is_ready(self) -> bool:
        """Return True if model is loaded and ready for inference."""
        return (
            self._loaded
            and self._real_backend is not None
            and self._real_backend.is_ready()
        )

    def tokenize(self, text: str) -> int:
        """Count tokens using the already-loaded inference model's tokenizer.

        If the model is not loaded, returns a conservative heuristic estimate.
        Does NOT trigger a model load.
        """
        if not text:
            return 0
        backend = self._real_backend
        if backend is not None and backend.is_ready():
            return backend.tokenize(text)
        # Fallback: conservative 2 chars/token
        return max(1, len(text) // 2)

    def tokenize_exact(self, text: str):
        """Return exact token count if model is loaded, else None."""
        backend = self._real_backend
        if backend is not None and backend.is_ready():
            return backend.tokenize_exact(text)
        return None

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
            source="llama_cpp_native_embedded",
        )

    def health_check(self):
        from brain.providers.base import ProviderHealth
        from datetime import datetime, timezone
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
            healthy=self.is_ready(),
            checked_at=checked_at,
            model_count=len(models),
        )

    def chat(self, request: ModelRequest) -> ModelResponse:
        model = request.model or self.default_model

        if not self.load_model():
            raise ProviderError(
                "model_missing",
                "Embedded GGUF model weights could not be verified or loaded for real inference",
            )

        messages = list(request.messages)
        user_prompt = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_prompt = msg.get("content", "")
                break

        lowered = user_prompt.lower()
        tool_calls = []

        # ---- Deterministic tool-call routing for system/tool commands ----
        # These are explicitly recognized action intents and remain
        # deterministic (they are not presented as model-generated reasoning).
        action, tool_name, target_path, target_action = self._extract_intent_from_prompt(user_prompt)

        if action in ("create", "read", "write", "list", "delete", "execute", "health"):
            if tool_name == "workspace.list" and action in ("list", "create"):
                tool_calls.append(ToolCall(
                    call_id="embedded_tool_call_1",
                    name=tool_name,
                    arguments={"relative_path": target_path or ""},
                ))
            elif tool_name == "file.read" and action == "read":
                tool_calls.append(ToolCall(
                    call_id="embedded_tool_call_2",
                    name=tool_name,
                    arguments={"relative_path": target_path or ""},
                ))
            elif tool_name == "file.write" and action in ("write", "create"):
                tp = target_path
                if ("python" in user_prompt.lower() or "بايثون" in user_prompt) and not tp.endswith(".py"):
                    tp = tp + ".py"
                tool_calls.append(ToolCall(
                    call_id="embedded_tool_call_3",
                    name=tool_name,
                    arguments={
                        "relative_path": tp or "",
                        "content": self._default_content(action, tool_name, tp, user_prompt),
                        "allow_overwrite": False,
                    },
                ))
            elif tool_name == "file.write" and action == "delete":
                tool_calls.append(ToolCall(
                    call_id="embedded_tool_call_5",
                    name=tool_name,
                    arguments={"relative_path": target_path or "", "content": "", "allow_overwrite": False},
                ))
            elif tool_name == "system.health" and action == "health":
                tool_calls.append(ToolCall(
                    call_id="embedded_tool_call_6",
                    name=tool_name,
                    arguments={},
                ))

        # For deterministic tool-call requests, return empty content (tool
        # calls carry the action). For everything else, delegate to the real
        # llama-cpp backend for genuine token generation.
        if tool_calls and not user_prompt.strip():
            # Tool-only request with no natural-language body.
            return ModelResponse(
                content="",
                provider=self.name,
                model=model,
                tool_calls=tuple(tool_calls),
                finish_reason="stop",
                usage={"prompt_eval_count": 0, "eval_count": 0, "backend": "llama_cpp_deterministic"},
            )

        if tool_calls:
            # Tool-call intent detected: emit tool calls AND real model
            # reasoning, generated by the actual GGUF weights.
            real_response = self._delegate_to_real(request)
            return ModelResponse(
                content=real_response.content,
                provider=self.name,
                model=model,
                tool_calls=tuple(tool_calls),
                finish_reason=real_response.finish_reason,
                usage=real_response.usage,
            )

        # General natural-language prompt -> genuine model inference.
        real_response = self._delegate_to_real(request)
        return ModelResponse(
            content=real_response.content,
            provider=self.name,
            model=model,
            tool_calls=real_response.tool_calls,
            finish_reason=real_response.finish_reason,
            usage=real_response.usage,
        )

    def _delegate_to_real(self, request: ModelRequest) -> ModelResponse:
        backend = self._ensure_backend()
        return backend.chat(request)

    def _extract_intent_from_prompt(self, user_prompt: str) -> Tuple[str, str, str, str]:
        """Extract action intent from natural language prompt.

        Returns a tuple of (action, tool_name, target_path, target_action).
        Supports English and Arabic phrasing for common file/system operations.
        """
        lowered = user_prompt.lower()
        # English action verbs
        en_create = any(w in lowered for w in ("create", "make", "new", "mkdir", "mkdirp"))
        en_read = any(w in lowered for w in ("read", "show", "cat", "open", "contents"))
        en_list = any(w in lowered for w in ("list", "ls", "dir", "enumerate"))
        en_write = any(w in lowered for w in ("write", "save", "put", "store"))
        en_delete = any(w in lowered for w in ("delete", "remove", "rm", "erase"))
        en_health = any(w in lowered for w in ("health", "status", "system"))
        en_execute = any(w in lowered for w in ("run", "execute", "start", "launch"))

        # Detect Arabic script presence
        arabic_script = bool(re.search(r'[\u0600-\u06FF]', user_prompt))

        # ---- Memory intent detection (formation vs recall) ---- (transliterated/common) - only actual verbs
        ar_create = any(w in user_prompt for w in ("أنشئ", "أنشاء", "أضف", "اصنع", "ابنِ", "ابن"))
        ar_read = any(w in user_prompt for w in ("اقرأ", "اقرء", "أظهر", "أظهر محتوى", "افتح", "أعرض"))
        ar_list = any(w in user_prompt for w in ("قائمة", "أعرض الملفات", "الأصول", "المجلدات", "المحتوى"))
        ar_write = any(w in user_prompt for w in ("اكتب", "احفظ", "ضع", "خزن", "أنشئ ملف", "أضف ملف"))
        ar_delete = any(w in user_prompt for w in ("احذف", "احذف ملف", "احذف مجلد", "امسح", "احذف العنصر"))
        ar_health = any(w in user_prompt for w in ("حالة", "نظام", "صحة", "طاقة", "ذاكرة"))
        ar_execute = any(w in user_prompt for w in ("نفذ", "أطلق", "ابدأ", "شغل"))

        target_path = ""
        target_action = ""

        # Extract a simple folder/file name: after "named", "named by", "at", "to", "in", "اسم", "باسم", "في المسار", "في المسار"
        path_match = re.search(
            r'(?:named\s+|named\s+by\s+|at\s+|to\s+|in\s+|اسم\s+(?:ملف|مجلد)?\s*|باسم\s+(?:ملف|مجلد)?\s*|في\s+(?:المسار|مسار)?\s*)([^\s\.]+)',
            user_prompt,
            re.IGNORECASE,
        )
        if path_match:
            target_path = path_match.group(1)

        # ---- Memory intent detection (formation vs recall) ----
        # Formation markers: imperative "store this fact" phrasing.
        is_memory_formation = (
            any(w in user_prompt for w in (
                "افتكر ان", "افتكر أن", "افتكر أن", "خلي بال", "خلي_بال",
                "احفظ المعلومة", "احفظ_المعلومة", "احفظ معلومة", "سجل ان",
                "سجّل ان", "خزن ان",
            ))
            or any(w in lowered for w in (
                "remember that", "remember this", "remember_this", "rememberthis",
                "keep in mind", "keep_in_mind", "save this", "save_this",
                "note this", "note_this", "note that", "store this", "store_that",
            ))
            # Bare "remember <fact>" (no interrogative form) is treated as formation.
            or ("remember" in lowered and "?" not in user_prompt and "؟" not in user_prompt)
            or (("افتكر" in user_prompt or "احفظ" in user_prompt)
                and "?" not in user_prompt and "؟" not in user_prompt)
        )

        # Recall markers: interrogative form asking the system to surface a fact.
        is_memory_recall = (
            any(w in user_prompt for w in (
                "ما هو", "ما هي", "ما هي", "ما هم", "ماذا", "ايه هو", "ايه هي",
                "إيه هو", "إيه هي", "إيه هو", "أين", "اين", "متى", "من هو", "من هي",
                "تفتكر", "فاكر", "بتفتكر", "تتذكر", "بتتذكر", "افتكرلي",
                "ذكرني", "فكرني", "بتحفظ", "هل تعرف", "هل تتذكر",
            ))
            or any(w in lowered for w in (
                "what is", "what's", "what was", "who is", "who's", "where is",
                "when is", "how much", "how many", "tell me", "do you remember",
                "do you know", "can you recall", "recall the", "remind me",
                "what did i", "what do you know about",
            ))
        )

        # Recall takes precedence over formation for interrogative phrasing, and
        # both take precedence over generic file/list routing so that a question
        # like "ما هو اسم المشروع؟" does not degrade into workspace.list.
        if is_memory_recall:
            return ("", "", "", "recall")
        if is_memory_formation:
            return ("", "", "", "remember")

        if arabic_script:
            if ar_create:
                target_action = "create"
                return ("write", "file.write", target_path or "", target_action)
            if ar_read:
                return ("read", "file.read", target_path or "", target_action)
            if ar_list:
                return ("list", "workspace.list", target_path or "", target_action)
            if ar_write:
                return ("write", "file.write", target_path or "", target_action)
            if ar_delete:
                return ("delete", "file.write", target_path or "", target_action)
            if ar_health:
                return ("health", "system.health", "", target_action)
            if ar_execute:
                return ("execute", "system.health", "", target_action)

        # English
        if en_list:
            return ("list", "workspace.list", target_path or "", target_action)
        if en_create:
            return ("write", "file.write", target_path or "", target_action)
        if en_read:
            return ("read", "file.read", target_path or "", target_action)
        if en_write:
            return ("write", "file.write", target_path or "", target_action)
        if en_delete:
            return ("delete", "file.write", target_path or "", target_action)
        if en_health:
            return ("health", "system.health", "", target_action)
        if en_execute:
            return ("execute", "system.health", "", target_action)

        # Fallback: any recognized verb without path -> list workspace
        if any(
            w in lowered
            for w in ("file", "files", "folder", "directory", "workspace", "مشروع", "مشروعات", "ملفات")
        ):
            return ("list", "workspace.list", "", target_action)

        return ("", "", "", "")

    def _generate_plan_json(self, user_prompt: str) -> str:
        """Generate a minimal valid JSON plan for simple objectives.
        Returns JSON string that LivePlanner can parse into an executable contract.
        """
        lowered = user_prompt.lower()
        if any(w in lowered for w in ("hello", "who are you", "hi", "identify", "explain")):
            return json.dumps({
                "objective": user_prompt,
                "steps": [
                    {
                        "step_id": "1",
                        "name": "system.health",
                        "tool": "system.health",
                        "arguments": {},
                        "dependencies": [],
                        "expected_result": "System health status",
                        "verification": "status == 'ok'",
                        "risk": "read"
                    }
                ]
            })
        return json.dumps({
            "objective": user_prompt,
            "steps": [
                {
                    "step_id": "1",
                    "name": "workspace.list",
                    "tool": "workspace.list",
                    "arguments": {},
                    "dependencies": [],
                    "expected_result": "Workspace file listing",
                    "verification": "isinstance(result, list)",
                    "risk": "read"
                }
            ]
        })

    def _default_content(self, action: str, tool_name: str, target_path: str, request_text: str) -> str:
        """Generate reasonable file content when the user did not supply it."""
        name = Path(target_path).name if target_path else "file"
        if tool_name == "file.write" and name.lower().endswith(".py"):
            return (
                "# Created by SEED\n"
                f'# Source: {request_text[:80]}\n'
                "\n"
                "def main():\n"
                f"    print('hello from SEED')\n"
                "\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            )
        return f"# Created by SEED\n{request_text}\n"
