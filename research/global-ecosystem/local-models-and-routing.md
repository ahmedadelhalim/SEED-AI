# SEED-AI Local Models and Model Routing

**Document Purpose:** Investigation of Ollama, llama.cpp, vLLM, and LiteLLM for robust local-first model execution.

---

## 1. Gateway Architecture
`ModelGateway` (`brain/model_gateway.py`) acts as the single abstraction layer between SEED's orchestrator and model providers (`OllamaProvider`, `OmniRouteProvider`).
- **Capability Gating:** Automatically inspects provider model metadata; rejects tool-calling requests for models lacking advertised capability (fail-closed).
- **Default Local Routing:** Defaults to Ollama (`http://127.0.0.1:11434`) running `qwen3:4b`.
- **Environment Alignment:** Requires `OLLAMA_MODELS=D:\AI\Models` to discover pre-downloaded model weights correctly.
