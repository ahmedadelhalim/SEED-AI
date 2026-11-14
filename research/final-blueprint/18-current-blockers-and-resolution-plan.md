# 18-Current Blockers and Resolution Plan

**Document ID:** `18-current-blockers-and-resolution-plan`
**Date:** 2026-11-12

---

1. **Ollama Daemon Environment Disconnect:**
   - *Root Cause:* Running Ollama PID 3132 lacks `OLLAMA_MODELS=D:\AI\Models`.
   - *Resolution:* Restart Ollama with the correct environment variable.
2. **Python 3.14.4 Windows Compatibility for Heavy ML/Audio Runtimes:**
   - *Root Cause:* Prebuilt binary wheels for certain C-extension ML and vector/audio libraries may lag behind Python 3.14 releases on Windows.
   - *Resolution:* Isolate heavy model execution, vector embedding generation, and STT/TTS workloads in standalone subprocesses running compatible isolated Python environments (e.g. Python 3.11/3.12) communicating via secure loopback IPC or structured JSON-RPC.
