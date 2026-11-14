# 12-Security and Governance Specification

**Document ID:** `12-security-and-governance-specification`
**Date:** 2026-11-12

---

## 1. Governance Model
- **Default-Deny:** Unregistered tools or scope mismatches are denied.
- **Approvals:** Cryptographic argument and identity digests (SHA-256), single-use consumption, and TTL expiration.
- **Perimeter Defense:** `WorkspaceGuard` blocks absolute paths, traversals (`..`), and symlinks.
- **Audit Logging:** Complete event streams (`events` table) recording permission outcomes and tool execution results.
