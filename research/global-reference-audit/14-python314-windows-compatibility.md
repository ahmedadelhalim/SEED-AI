# 14-Python 3.14 and Windows Compatibility

**Document ID:** `14-python314-windows-compatibility`
**Date:** 2026-11-12

---

## 1. Compatibility Strategy
- Lightweight Python modules run in-process.
- Heavy C-extension ML, vector embedding, and audio runtimes are isolated in standalone subprocesses running compatible Python interpreters (e.g. Python 3.11/3.12) communicating via secure loopback JSON-RPC.
