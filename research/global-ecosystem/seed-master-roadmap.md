# SEED-AI Master Completion Roadmap

**Document Purpose:** Phased engineering roadmap to complete SEED-AI into a production-grade personal AI operating assistant for Windows.

---

## Phased Roadmap

- **Phase 1: Foundation Hardening & Runtime Resilience** *(Completed)*
  - Task lifecycle state machine, startup orphan reconciliation, and governed filesystem tools (`file.read`, `file.search`, `file.write`).
- **Phase 2: Windows System Control & Host Automation** *(Next)*
  - App launching via Start Menu / `shell:AppsFolder`, window management, global hotkeys (PTT), and Windows DPAPI credential encryption.
- **Phase 3: Browser Automation via Governed Playwright**
  - Playwright Python adapter with SSRF guards and write action approvals.
- **Phase 4: Persistent Semantic & Episodic Memory (Qdrant + Mem0 Patterns)**
  - Embedded Qdrant vector store and automated fact extraction.
- **Phase 5: Real-Time Voice & Audio Engine**
  - Silero VAD, openWakeWord "Hey SEED", streaming Whisper STT, and Piper/Kokoro TTS with barge-in support.
- **Phase 6: Desktop Presentation & Tray Integration**
  - Floating Smart Orb overlay, Win32 system tray, SSE token streaming, and subagent delegation.
