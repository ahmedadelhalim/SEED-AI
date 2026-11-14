# 02-Repository Architecture Audit

**Document ID:** `02-repository-architecture-audit`
**Date:** 2026-11-12

---

## 1. Architectural Invariant Check
- **Single Central Authority:** **VERIFIED**. All entry points (`desktop_server.py`, `seed_mcp_server.py`) delegate exclusively to `SeedApplication.seed_request()`.
- **Bypass Prevention:** No third-party skill, MCP server, or client can execute tools without passing through `ToolRegistry`, `PermissionEngine`, and `ApprovalManager`.
- **Test Integrity:** All 66 unit and integration tests execute successfully in isolated temporary databases.
