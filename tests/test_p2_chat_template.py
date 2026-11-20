"""P2 Chat Template Accounting validation tests."""
import pytest


def test_arabic_parity():
    from brain.providers.llama_real import RealLlamaProvider
    p = RealLlamaProvider()
    p.load_model()
    msgs = [{"role": "system", "content": "أنت مساعد مفيد."}, {"role": "user", "content": "مرحبا"}]
    cnt = p.count_chat_tokens(msgs)
    r = p._model.create_chat_completion(messages=msgs, max_tokens=1)
    assert cnt == r["usage"]["prompt_tokens"]


def test_english_parity():
    from brain.providers.llama_real import RealLlamaProvider
    p = RealLlamaProvider()
    p.load_model()
    msgs = [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Hello"}]
    cnt = p.count_chat_tokens(msgs)
    r = p._model.create_chat_completion(messages=msgs, max_tokens=1)
    assert cnt == r["usage"]["prompt_tokens"]


def test_mixed_parity():
    from brain.providers.llama_real import RealLlamaProvider
    p = RealLlamaProvider()
    p.load_model()
    msgs = [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Hello مرحبا"}]
    cnt = p.count_chat_tokens(msgs)
    r = p._model.create_chat_completion(messages=msgs, max_tokens=1)
    assert cnt == r["usage"]["prompt_tokens"]


def test_multiturn_parity():
    from brain.providers.llama_real import RealLlamaProvider
    p = RealLlamaProvider()
    p.load_model()
    msgs = [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}, {"role": "user", "content": "Bye"}]
    cnt = p.count_chat_tokens(msgs)
    r = p._model.create_chat_completion(messages=msgs, max_tokens=1)
    assert cnt == r["usage"]["prompt_tokens"]


def test_empty_history():
    from brain.providers.llama_real import RealLlamaProvider
    p = RealLlamaProvider()
    p.load_model()
    msgs = [{"role": "user", "content": ""}]
    cnt = p.count_chat_tokens(msgs)
    r = p._model.create_chat_completion(messages=msgs, max_tokens=1)
    assert cnt == r["usage"]["prompt_tokens"]


def test_context_limit():
    from core.intelligence import ContextAssembler
    assert ContextAssembler.enforce_context_limit(100, 256, 8192) is True
    assert ContextAssembler.enforce_context_limit(8000, 256, 8192) is False


def test_embedded_delegation():
    from brain.providers.llama_embedded import EmbeddedLlamaProvider
    p = EmbeddedLlamaProvider()
    p.load_model()
    msgs = [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Hello"}]
    cnt = p.count_chat_tokens(msgs)
    assert cnt == 20


def test_intelligence_integration():
    from core.intelligence import set_shared_tokenizer_provider, ContextAssembler
    from brain.providers.llama_real import RealLlamaProvider
    p = RealLlamaProvider()
    p.load_model()
    set_shared_tokenizer_provider(p)
    msgs = [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Hello"}]
    cnt = ContextAssembler.count_chat_tokens(msgs)
    assert cnt == 20
    assert ContextAssembler.enforce_context_limit(cnt, 256, 8192) is True