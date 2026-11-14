# SEED-AI Security and Governance

**Document Purpose:** Comprehensive review of SEED-AI's security invariants, default-deny policies, approval workflows, and credential protection.

---

## 1. Core Security Invariants
1. **Default-Deny Authorization:** Any unregistered tool or unauthorized scope/action defaults to `DENY`.
2. **Granular Scoping & Policy Checks:** Every operation passes through `PermissionEngine.check()`.
3. **Cryptographic Approvals:** Approvals bind the complete execution identity and argument digest (SHA-256), enforcing single-use and TTL expiration.
4. **Idempotency Guarantees:** Prevents duplicate execution of critical operations.
5. **Audit Trail:** Every action records structured task events and audit logs in SQLite.
