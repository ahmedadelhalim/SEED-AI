# 09-Model and Inference Comparison

**Document ID:** `09-model-and-inference-comparison`
**Date:** 2026-11-12

---

## 1. Provider-Independent Gateway
- `ModelGateway` (`brain/model_gateway.py`) abstracts Ollama and OmniRoute.
- Enforces capability gating (fails closed if tool calling is unsupported).
