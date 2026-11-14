# 17-Open Decisions and User Approvals

**Document ID:** `17-open-decisions-and-user-approvals`
**Date:** 2026-11-12

---

## Approved Decisions (Recorded 2026-11-12)

1. **Third-Party Skill Trust Policy (MANUAL):** Approved. Every third-party skill requires administrative review, provenance inspection, and cryptographic digest (`sha256`) binding. Skills cannot grant themselves permissions. Installation and activation are separate. Any artifact modification invalidates approval.
2. **MCP Server Trust Policy (EXPLICIT):** Approved. Discovered MCP servers remain inactive until explicitly configured in `mcp_servers.json` and approved. Changes to server identity, command, credentials, or requested permissions trigger revalidation and renewed approval.
3. **Ollama Environment Alignment:** User approval required to restart the Ollama background service with `OLLAMA_MODELS=D:\AI\Models`.

## Remaining Unresolved Decisions

1. **Vector Store Selection:** Confirm embedded Qdrant vs. SQLite FTS5 for semantic vector search in Phase 5.
2. **Voice Engine Selection:** Confirm Whisper/Piper vs. cloud-compatible runtimes for Phase 6 real-time voice.
