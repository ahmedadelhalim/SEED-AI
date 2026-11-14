# 07-Internet and Browser Research

**Document ID:** `07-internet-and-browser-research`
**Date:** 2026-11-12

---

## 1. Browser Automation Architecture
- Governed Playwright Python adapter (`runtime/browser_adapter.py`).
- Strict SSRF guards blocking loopback (`127.0.0.1`, `localhost`) and metadata endpoints (`169.254.169.254`).
- Read actions require read permission; state-changing actions (`browser.click`, `browser.fill_form`) require explicit human approval via `ApprovalManager`.
