# 04-Target Architecture & Subsystem Specification

**Document ID:** `04-target-architecture`
**Date:** 2026-11-12

---

## 1. Subsystems
1. **Application & Transport Layer:** `SeedApplication`, Desktop HTTP/SSE server, MCP stdio server.
2. **Central Intelligence & Orchestration:** `SeedOrchestrator`, `TaskEngine`, `CancellationToken`.
3. **Model Gateway:** `ModelGateway`, `OllamaProvider`, `OmniRouteProvider`.
4. **Memory & Knowledge Layer:** SQLite relational store + embedded Qdrant vector store.
5. **Skills & Tools Engine:** Manifest-driven skill loader + `ToolRegistry`.
6. **Internet & Browser Layer:** Governed Playwright adapter with SSRF guards.
7. **Windows Control Layer:** Win32 discovery, app/process management, service control, DPAPI credentials.
8. **Security & Governance:** `PermissionEngine`, `ApprovalManager`, `IdempotencyGuard`, `WorkspaceGuard`.
