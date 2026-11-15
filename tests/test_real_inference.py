"""Real inference integration tests.

These tests exercise the genuine llama-cpp-python backend. They are marked so
that they can be skipped on machines that do not have the model artifact or
the ``llama_cpp`` package installed.

Run with::

    .venv\\Scripts\\python.exe -m pytest tests/test_real_inference.py -v

Skip real-inference tests with::

    set SEED_SKIP_REAL_INFERENCE=1

Distinction:
- ``MockedProviderTests`` uses no model. It proves wiring, not the model.
- ``RealInferenceTests`` loads the actual 2.33 GB GGUF weights and generates
  tokens. It proves real inference.
"""

import os
import unittest

from brain.model_gateway import ModelGateway
from brain.model_types import ModelRequest
from brain.providers.base import ProviderError
from brain.providers.llama_embedded import EmbeddedLlamaProvider
from brain.providers.llama_real import RealLlamaProvider


DEFAULT_MODEL_PATH = (
    "D:/AI/Models/blobs/"
    "sha256-3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f"
)
MODEL_PATH = os.environ.get("SEED_MODEL_PATH", DEFAULT_MODEL_PATH)


def _llama_cpp_available() -> bool:
    try:
        import llama_cpp  # noqa: F401
        return True
    except Exception:
        return False


REAL_INFERENCE_AVAILABLE = bool(
    _llama_cpp_available()
    and os.path.exists(MODEL_PATH)
    and os.environ.get("SEED_SKIP_REAL_INFERENCE", "").strip().lower()
    not in ("1", "true", "yes")
)
SKIP_REASON = (
    "Real inference unavailable: requires the llama_cpp package, the GGUF "
    "model artifact at SEED_MODEL_PATH, and SEED_SKIP_REAL_INFERENCE unset"
)


class ArtifactValidationTests(unittest.TestCase):
    """Deterministic artifact checks (no inference)."""

    def test_gguf_artifact_is_real_weights_file(self):
        self.assertTrue(os.path.exists(MODEL_PATH), "GGUF artifact missing")
        size = os.path.getsize(MODEL_PATH)
        # A 4B Q4_K quantized model is ~2.3 GB. Guard against stub files.
        self.assertGreater(size, 1_000_000_000, "GGUF artifact too small to be real weights")
        with open(MODEL_PATH, "rb") as handle:
            self.assertEqual(handle.read(4), b"GGUF", "Bad GGUF magic")

    def test_capabilities_advertise_real_inference(self):
        caps = EmbeddedLlamaProvider().capabilities("qwen3:4b")
        self.assertTrue(caps.tool_calling)
        self.assertTrue(caps.streaming)
        self.assertIn("real_inference", caps.features)
        self.assertIn("llama_cpp", caps.features)


class MockedProviderTests(unittest.TestCase):
    """Wiring tests only. These do NOT prove inference."""

    def test_gateway_registers_both_inference_providers(self):
        gateway = ModelGateway.with_local_defaults()
        self.assertIn("llama_embedded", gateway.provider_names)
        self.assertIn("llama_real", gateway.provider_names)

    def test_default_provider_is_configurable_to_llama_real(self):
        gateway = ModelGateway.with_local_defaults(default_provider="llama_real")
        self.assertEqual(gateway.default_provider, "llama_real")

    def test_invalid_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            ModelGateway.with_local_defaults(default_provider="not_a_provider")


class ReadinessSemanticsTests(unittest.TestCase):
    """Readiness must not be claimed before weights are actually loaded."""

    def test_embedded_reports_not_ready_before_load(self):
        self.assertFalse(EmbeddedLlamaProvider().is_ready())

    def test_real_provider_reports_not_ready_before_load(self):
        self.assertFalse(RealLlamaProvider().is_ready())

    def test_missing_model_path_raises_provider_error(self):
        provider = RealLlamaProvider(model_path="D:/definitely/not/here.gguf")
        with self.assertRaises((ProviderError, ValueError)):
            provider.chat(ModelRequest(
                messages=(dict(role="user", content="hi"),),
            ))


@unittest.skipUnless(REAL_INFERENCE_AVAILABLE, SKIP_REASON)
class RealInferenceTests(unittest.TestCase):
    """Genuine inference against the real GGUF weights."""

    provider = None

    @classmethod
    def setUpClass(cls):
        cls.provider = RealLlamaProvider()
        assert cls.provider.load_model(), "real model failed to load"

    @classmethod
    def tearDownClass(cls):
        if cls.provider is not None:
            cls.provider.unload_model()

    def test_real_load_sets_ready(self):
        self.assertTrue(self.provider.is_ready())
        self.assertEqual(self.provider.list_models(), ("qwen3:4b",))

    def test_real_generation_is_not_a_template(self):
        response = self.provider.chat(ModelRequest(
            messages=(dict(role="user", content="Reply with the single word: pong"),),
            model="qwen3:4b",
        ))
        self.assertEqual(response.provider, "llama_real")
        self.assertEqual(response.usage.get("backend"), "llama_cpp")
        self.assertTrue(response.content.strip(), "model produced no tokens")
        self.assertGreater(response.usage.get("completion_tokens", 0), 0)
        self.assertNotIn(
            "SEED in-process runtime processed your request successfully",
            response.content,
        )

    def test_real_generation_differs_across_prompts(self):
        first = self.provider.chat(ModelRequest(
            messages=(dict(role="user", content="Name one primary colour."),),
        ))
        second = self.provider.chat(ModelRequest(
            messages=(dict(role="user", content="Name one animal that barks."),),
        ))
        self.assertNotEqual(first.content, second.content)

    def test_real_streaming_yields_incremental_tokens(self):
        chunks = []
        stream = self.provider.chat_stream(
            ModelRequest(messages=(dict(role="user", content="Count from one to three."),)),
            lambda token: chunks.append(token),
        )
        final = ""
        for chunk in stream:
            final = chunk
        self.assertTrue(chunks, "streaming produced no chunk callbacks")
        self.assertTrue(final.strip(), "streaming produced no content")

    def test_embedded_delegates_to_real_backend(self):
        # Only one 2.33 GB GGUF can be resident at a time in this process, so
        # release the class-level model before constructing a second provider.
        type(self).provider.unload_model()
        provider = EmbeddedLlamaProvider()
        try:
            self.assertTrue(provider.load_model())
            self.assertTrue(provider.is_ready())
            response = provider.chat(ModelRequest(
                messages=(dict(role="user", content="Say goodbye in one short sentence."),),
            ))
            self.assertEqual(response.provider, "llama_embedded")
            self.assertEqual(response.usage.get("backend"), "llama_cpp")
            self.assertTrue(response.content.strip())
        finally:
            provider.unload_model()
            type(self).provider.load_model()

    def test_embedded_keeps_deterministic_tool_routing(self):
        # Deterministic routing triggers no inference, so the class-level
        # model can stay resident.
        provider = EmbeddedLlamaProvider()
        try:
            # Delegate readiness to the already-loaded class-level weights.
            provider._real_backend = type(self).provider
            provider._loaded = True
            response = provider.chat(ModelRequest(
                messages=(dict(role="user", content="list files in workspace"),),
            ))
            self.assertTrue(response.tool_calls)
            self.assertEqual(response.tool_calls[0].name, "workspace.list")
        finally:
            provider._real_backend = None
            provider._loaded = False


if __name__ == "__main__":
    unittest.main(verbosity=2)