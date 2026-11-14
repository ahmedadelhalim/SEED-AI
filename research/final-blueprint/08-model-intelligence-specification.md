# 08-Model Intelligence Specification

**Document ID:** `08-model-intelligence-specification`
**Date:** 2026-11-12

---

## 1. Gateway & Routing
- `ModelGateway` (`brain/model_gateway.py`) abstracts provider communication.
- **Capability Gating:** Rejects tool-calling requests for models lacking advertised capability.
- **Fallback & Health:** Non-probing health checks; configurable provider fallback (`Ollama` primary, `OmniRoute` secondary).
- **Security Invariant:** Models propose tool calls; SEED independently validates schemas, checks permissions, and enforces approvals before execution.
