# SEED-AI Phase 2 Acceptance Plan

**Document Purpose:** Acceptance criteria and test plan for Phase 2 (Windows System Control & Host Automation) once authorized.

---

## Phase 2 Objectives

Implement secure Windows system control tools:
1. **Application Launcher (`windows.launch_app`):** Discover installed desktop/Store apps via `shell:AppsFolder`, validate against an allowlist, and require human approval for unlisted apps.
2. **Window Management (`windows.get_active_window`, `windows.focus_window`):** Read foreground window titles and manage focus safely.
3. **Credential Storage (`security/credentials.py`):** Provide Windows DPAPI-backed encryption at rest for sensitive credentials (`CryptProtectData` / `CryptUnprotectData`).
4. **Global Hotkeys:** Register native hotkeys (e.g., `Ctrl+Win`) for Push-to-Talk and assistant activation.

## Acceptance Criteria & Test Suite

- **Unit Test:** `test_windows_app_launcher_denies_unlisted_executables()` verifies arbitrary `.bat`/`.exe` execution is blocked.
- **Unit Test:** `test_dpapi_encryption_roundtrip()` confirms secure secret encryption/decryption using Windows DPAPI.
- **Integration Test:** `windows.launch_app` successfully launches an approved application under human approval and captures process metadata.
- **Regression Suite:** Complete existing 70-test suite must pass 100% without regressions.
