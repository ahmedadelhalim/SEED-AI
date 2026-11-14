# 15-Acceptance Test Catalog

**Document ID:** `15-acceptance-test-catalog`
**Date:** 2026-11-12

---

## Verification Plan
- **Unit Tests:** Validate schema validation, permission checks, approval hashing, idempotency caching, and workspace path containment.
- **Integration Tests:** Exercise `SeedApplication.seed_request()` across Desktop and MCP transports.
- **Security Tests:** Verify default-deny behavior, path traversal rejection, symlink escape denial, approval TTL expiration, and audit logging.
- **Regression Suite:** Complete execution of all registered unit tests under `.venv` without regression.
