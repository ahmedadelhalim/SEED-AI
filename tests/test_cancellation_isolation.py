import threading
import time
import unittest
from unittest import TestCase
from unittest.mock import patch

from brain.model_types import ModelRequest, ModelResponse
from brain.providers.base import ProviderError
from brain.providers.llama_real import RealLlamaProvider


class CancellationIsolationTests(TestCase):
    def test_legacy_request_compatibility_and_different_tokens(self):
        req1 = ModelRequest(messages=({"role": "user", "content": "hi"},))
        req2 = ModelRequest(messages=({"role": "user", "content": "hello"},))
        
        token1 = getattr(req1, "cancellation_token", None) or threading.Event()
        token2 = getattr(req2, "cancellation_token", None) or threading.Event()
        
        self.assertIsNone(req1.cancellation_token)
        self.assertIsNone(req2.cancellation_token)
        self.assertIsNot(token1, token2)

    def test_cancelling_token_a_does_not_affect_token_b(self):
        token_a = threading.Event()
        token_b = threading.Event()
        
        token_a.set()
        
        self.assertTrue(token_a.is_set())
        self.assertFalse(token_b.is_set())

    def test_provider_cancel_with_specific_token(self):
        provider = RealLlamaProvider()
        token_a = threading.Event()
        token_b = threading.Event()
        
        provider.cancel(token_a)
        
        self.assertTrue(token_a.is_set())
        self.assertFalse(token_b.is_set())
        self.assertFalse(provider._cancel_event.is_set())


if __name__ == "__main__":
    unittest.main()
