# 03-Technology Selection & Compatibility

**Document ID:** `03-technology-selection`
**Date:** 2026-11-12

---

## 1. Selected Stack & Compatibility (Python 3.14.4 / Windows 11)
- **Core Orchestration & Security:** Python standard library (`sqlite3`, `ctypes`, `hashlib`, `asyncio`, `threading`) + `pydantic` / `jsonschema`.
- **Database & Storage:** SQLite 3 (WAL mode) for relational state; Qdrant (local embedded mode) for semantic vector search.
- **Model Gateway:** Native REST client (`urllib.request` / `httpx`) supporting Ollama and OpenAI-compatible endpoints.
- **Browser Automation:** Playwright Python (`playwright`) wrapped in governed SEED tools with SSRF protection.
- **Voice Runtime:** Whisper / faster-whisper (or cloud/subprocess fallback), Silero VAD ONNX, Piper / Kokoro-ONNX for TTS.
- **Windows Integration:** `psutil`, `pywin32` (`win32api`, `win32gui`, `win32process`), and Windows DPAPI via `ctypes` / `cryptography`.
