# 11-Voice, Vision, and Avatar Specification

**Document ID:** `11-voice-vision-avatar-specification`
**Date:** 2026-11-12

---

## 1. Multimodal Interaction Contracts
- **Audio Pipeline:** `interfaces/media.py` defines abstract speech input/output adapters and wake-word privacy gates.
- **Privacy & Interruption:** Explicit opt-in for "Hey SEED" wake word and microphone capture; real-time barge-in support to cancel TTS playback and update the active session.
- **Visuals:** Desktop Smart Orb rendering 7 canonical presentation states driven exclusively by SEED orchestrator events.
