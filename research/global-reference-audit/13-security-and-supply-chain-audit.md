# 13-Security and Supply Chain Audit

**Document ID:** `13-security-and-supply-chain-audit`
**Date:** 2026-11-12

---

## 1. Governance Invariants
- Default-deny permission engine.
- Cryptographic argument-digested approvals with TTL expiration and replay protection.
- Workspace perimeter defense via `WorkspaceGuard`.
- Complete audit persistence in SQLite (`events` table).
