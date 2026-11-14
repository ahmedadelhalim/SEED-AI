# 21-Roadmap Reconciliation

**Document ID:** `21-roadmap-reconciliation`
**Date:** 2026-11-12
**Purpose:** Reconciles the implementation roadmap with the findings and conditional acceptance criteria of `20-blueprint-quality-audit.md`.

---

## 1. Reconciled Priority: Dynamic Skills, Tools, and MCP Engine
Per the audit recommendations, the implementation roadmap has been updated so that **Phase 3 (Dynamic Skills, Tools, and MCP Engine)** is prioritized immediately after foundation verification. This ensures that manifest-driven extensibility is fully established before layering complex Windows administration and browser automation tools.

## 2. Dependency Graph & Sequencing
1. **Phase 1 & 2A.1:** Core Foundation & Windows Discovery *(Completed & Verified)*
2. **Phase 3:** Dynamic Skills, Tools, and MCP Engine (`SKILL.md` parser, tool manifest verification, secure registration) *(Next)*
3. **Phase 2B–2F:** Windows System Control (App launching, process management, services, PowerShell, DPAPI)
4. **Phase 4:** Governed Internet & Browser Automation (Playwright with SSRF guards)
5. **Phase 5:** Persistent Semantic & Episodic Memory (Embedded Qdrant + Mem0)
6. **Phase 6 & 7:** Real-Time Voice Runtime & Desktop UI Polish

## 3. Governance and Security Rules Reaffirmed (Including User-Approved Policies)
- **Third-Party Skill Trust (MANUAL):** Every third-party skill requires administrative review, provenance inspection, and cryptographic digest (`sha256`) binding. Skills cannot grant themselves permissions.
- **MCP Server Trust (EXPLICIT):** Discovered MCP servers remain inactive until explicitly configured in `mcp_servers.json` and approved.
- **Central Authority Invariant:** All third-party skills, MCP servers, and external tools are treated as untrusted extensions. They must never bypass SEED's central execution path (`SeedApplication.seed_request()` → `SeedOrchestrator` → `ToolRegistry` → `PermissionEngine` → `ApprovalManager` → audit persistence).
- **Python 3.14.4 Compatibility Mitigation:** Heavy ML/audio runtimes will use isolated subprocesses with compatible Python interpreters.
