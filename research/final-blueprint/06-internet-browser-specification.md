# 06-Internet and Browser Intelligence Specification

**Document ID:** `06-internet-browser-specification`
**Date:** 2026-11-12

---

## 1. Browser Automation Architecture
- **Adapter:** `runtime/browser_adapter.py` powered by Playwright Python.
- **SSRF & Loopback Guards:** Blocks navigation to loopback (`127.0.0.1`, `localhost`), metadata endpoints (`169.254.169.254`), and SEED's local management ports unless explicitly approved.
- **Action Gating:** Read actions (`browser.navigate`, `browser.extract_content`, `browser.screenshot`) require read permissions; state-changing actions (`browser.click`, `browser.fill_form`) require explicit human approval via `ApprovalManager`.
