# 05-Feature-by-Feature Comparison

**Document ID:** `05-feature-by-feature-comparison`
**Date:** 2026-11-12

---

## Comparison Matrix

| Capability | Reference Standard | SEED Implementation | Classification |
|---|---|---|---|
| Orchestration Loop | LangGraph | `SeedOrchestrator` | `IMPLEMENTED_AND_VERIFIED` |
| Security / Permissions | Custom / GuardRails | `PermissionEngine` | `IMPLEMENTED_AND_VERIFIED` |
| Approvals & Idempotency | Custom Enterprise | `ApprovalManager` & `IdempotencyGuard` | `IMPLEMENTED_AND_VERIFIED` |
| MCP Server | MCP Python SDK | `interfaces/seed_mcp_server.py` | `IMPLEMENTED_AND_VERIFIED` |
| Dynamic Skills (`SKILL.md`) | Agent Skills Spec | Planned Phase 3 | `DESIGNED_ONLY` |
| Vector Memory | Qdrant / Chroma | Planned Phase 6 | `DESIGNED_ONLY` |
