import unittest
from brain.model_gateway import ModelGateway
from brain.model_types import ModelRequest
from brain.providers.llama_embedded import EmbeddedLlamaProvider


class EmbeddedProviderTests(unittest.TestCase):
    def test_embedded_provider_initialization(self):
        provider = EmbeddedLlamaProvider()
        self.assertEqual(provider.name, "llama_embedded")
        caps = provider.capabilities("qwen3:4b")
        self.assertTrue(caps.tool_calling)
        self.assertIn("embedded", caps.features)

    def test_model_gateway_with_embedded_default(self):
        gateway = ModelGateway.with_local_defaults(default_provider="llama_embedded")
        self.assertEqual(gateway.default_provider, "llama_embedded")
        self.assertIn("llama_embedded", gateway.provider_names)

        response = gateway.complete(ModelRequest(
            messages=({"role": "user", "content": "Please call system.health now."},),
            model="qwen3:4b",
            tools=({"type": "function", "function": {"name": "system.health", "parameters": {}}},),
        ))
        self.assertEqual(response.provider, "llama_embedded")
        self.assertTrue(response.tool_calls)
        self.assertEqual(response.tool_calls[0].name, "system.health")


if __name__ == "__main__":
    unittest.main(verbosity=2)
