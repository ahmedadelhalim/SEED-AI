# 01-Verified Current SEED State

**Document ID:** `01-verified-current-seed-state`
**Date:** 2026-11-12

---

## 1. Verified Implementation Inventory
- **Composition Root (`core/application.py`):** Unifies `SeedOrchestrator`, `TaskEngine`, `PermissionEngine`, `ToolRegistry`, `ModelGateway`, and `OperationsAPI`.
- **Central Orchestrator (`core/orchestrator.py`):** Bounded 8-step turn loop, tool call budget (16), parallel read safety, approval interception, and idempotency checking.
- **Security & Governance (`security/`):** Default-deny `PermissionEngine`, single-use argument-digested `ApprovalManager`, reentrant `IdempotencyGuard`, and strict `WorkspaceGuard`.
- **Persistence (`memory/store.py`):** Multi-table SQLite repository (`tasks`, `events`, `memory`, `sessions`, `session_messages`, `session_tasks`, `memory_items`, `approval_requests`, `idempotency_records`).
- **Interfaces (`interfaces/`):** MCP stdio server (`seed_mcp_server.py`) and loopback Desktop HTTP/SSE server (`desktop_server.py`).
- **Windows Discovery (`runtime/windows/`):** Read-only host, CPU, memory, disk, process, and network metrics (`system.windows_*`).

---
*Verified against active test suite (66 tests passing).*
