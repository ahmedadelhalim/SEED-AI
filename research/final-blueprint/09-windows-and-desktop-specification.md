# 09-Windows and Desktop Specification

**Document ID:** `09-windows-and-desktop-specification`
**Date:** 2026-11-12

---

## 1. Host Control Architecture
- **Discovery (Phase 2A):** Read-only host, CPU, memory, disk, process, and network metrics (`runtime/windows/discovery.py`).
- **Applications & Processes (Phase 2B):** `shell:AppsFolder` app launching via allowlists; process discovery and graceful termination requiring approval.
- **Services (Phase 2D):** Windows service inspection and controlled start/stop with approval.
- **PowerShell (Phase 2E):** Restricted PowerShell command execution with parameter allowlists, timeouts, and audit logging.
- **DPAPI Credentials (Phase 2F):** Windows `CryptProtectData` / `CryptUnprotectData` for secure secret encryption at rest.
