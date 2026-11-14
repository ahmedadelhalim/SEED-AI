# 13-Proposed Complete File Tree

**Document ID:** `13-proposed-complete-file-tree`
**Date:** 2026-11-12

---

## Complete Future Repository Structure

```
D:\SEED-AI\
├── brain/
│   ├── model_gateway.py (Preserve & Extend)
│   ├── model_types.py (Preserve)
│   └── providers/ (Preserve ollama.py, omniroute.py)
├── core/
│   ├── application.py (Preserve & Extend)
│   ├── orchestrator.py (Preserve)
│   ├── operations.py (Preserve)
│   ├── service_registry.py (Preserve)
│   ├── task_engine.py (Preserve)
│   └── tool_registry.py (Preserve)
├── runtime/
│   ├── agent_runtime.py (Preserve)
│   ├── browser_adapter.py (Create - Phase 3)
│   ├── file_tools.py (Preserve)
│   ├── workspace_guard.py (Preserve)
│   └── windows/
│       ├── discovery.py (Preserve - Phase 2A)
│       ├── management.py (Create - Phase 2B)
│       ├── services.py (Create - Phase 2D)
│       ├── powershell.py (Create - Phase 2E)
│       └── credentials.py (Create - Phase 2F)
├── security/
│   ├── approval_manager.py (Preserve)
│   ├── idempotency.py (Preserve)
│   └── permission_engine.py (Preserve & Extend)
├── memory/
│   ├── store.py (Preserve & Extend)
│   └── vector_store.py (Create - Phase 4)
├── interfaces/
│   ├── desktop_server.py (Preserve)
│   ├── media.py (Preserve & Extend - Phase 5)
│   ├── seed_mcp_server.py (Preserve)
│   └── tool_adapter.py (Preserve)
└── tests/ (Preserve & Extend across all phases)
```
