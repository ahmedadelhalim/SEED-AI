# SEED-AI Voice and Multimodal Interaction

**Document Purpose:** Investigation of real-time speech recognition, text-to-speech, voice activity detection, and multimodal contracts.

---

## 1. Subordinate Media Architecture
`interfaces/media.py` defines provider-neutral contracts (`SpeechTranscript`, `SpeechRequest`, `SpeechAudio`, `SpeechInputAdapter`, `SpeechOutputAdapter`, `WakeWordPolicy`).
- **Privacy First:** Wake-word activation (`Hey SEED`) and microphone capture are strictly opt-in with explicit user consent and a visible UI indicator.
- **Interruption Support:** Supports low-latency barge-in / speech interruption, canceling active audio playback and routing state back to the central SEED session.
- **Language Support:** Designed for bilingual Arabic (`ar_JO`) and English (`en_US`) processing via local ONNX runtimes.
