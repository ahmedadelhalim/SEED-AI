# SEED-AI Open-Source Integration & Capability Matrix

**Document Purpose:** Comprehensive evaluation of target open-source repositories, license analysis, Python 3.14/Windows compatibility, resource profiles, component classification, and architectural mapping for SEED-AI.
**Evaluation Standard:** Component-level integration only. SEED must remain the central intelligence, orchestrator, permission authority, and memory owner.

---

## 1. Candidate Classification Summary

Every evaluated project is classified into one of four integration tiers:
1. **Integrate as a Dependency:** Direct package inclusion or clean CLI/binary invocation under SEED tool governance.
2. **Adapt Selected Components:** Refactor specific algorithms, patterns, or data structures into SEED's clean architecture under SEED's license.
3. **Use as an Architectural Reference Only:** Study patterns for inspiration; do not import or copy code (e.g., due to license ambiguity, architectural divergence, or framework bloat).
4. **Reject:** Incompatible architecture, high security risk, unmaintained status, or direct conflict with SEED's governance.

| Candidate Project | Repository URL | License | Python & Windows Support | Classification | Rationale & Recommended Integration Scope |
|---|---|---|---|---|---|
| **A. Dodaios** | `github.com/Dodaios/Dodaios` | Apache-2.0 | Python 3.10-3.12, Windows/macOS/Linux | **Use as Architectural Reference Only** | Dodaios (formerly Personal Jarvis) is an entire desktop superagent application with its own Electron frontend, agents, and IDE panes. Importing it would displace SEED. Reference its multi-agent brief delegation patterns and human-in-the-loop approval levels (`safe`, `monitor`, `ask`, `block`). |
| **B. RealtimeSTT** | `github.com/KoljaB/RealtimeSTT` | Apache-2.0 (v1.2.0) | Python 3.11-3.12 (NOT 3.14 compatible), Windows compatible | **Adapt Selected Components / Isolated Service** | Excellent low-latency streaming STT with pause-detection (`live-flush` Preview). Because its C-extensions (PyAudio, CTranslate2, onnxruntime) lack Python 3.14 wheels, run it as an isolated loopback service (`stt-server-production --host 127.0.0.1 --port 8010`) subordinate to SEED's `SpeechInputAdapter`. |
| **C. Mem0** | `github.com/mem0ai/mem0` | Apache-2.0 | Python 3.10-3.12, Windows compatible | **Adapt Selected Components** | Multi-level memory (user, session, agent) with temporal reasoning and entity extraction. Adapt its fact extraction prompts, entity linking, and BM25+vector score fusion into SEED's `memory/store.py` backed by local Qdrant/SQLite. Reject its cloud SaaS dependencies. |
| **D. Playwright Python** | `github.com/microsoft/playwright-python` | Apache-2.0 | Python 3.8-3.14, Full Windows support | **Integrate as a Dependency** | Microsoft-backed, battle-tested browser automation with prebuilt driver. Wrap Playwright in SEED registered tools (`browser.navigate`, `browser.click`, `browser.snapshot`) subject to `PermissionEngine` URL allowlists and action approvals. |
| **E. Silero VAD** | `github.com/snakers4/silero-vad` | MIT | Python 3.8-3.14 via ONNX Runtime, Full Windows support | **Integrate as a Dependency** | Sub-millisecond voice activity detection on CPU (<2 MB model). Crucial for voice turn-taking and barge-in detection. Use via pure ONNX Runtime CPU to avoid PyTorch/TorchAudio dependencies in Python 3.14. |
| **F. Qdrant** | `github.com/qdrant/qdrant` | Apache-2.0 | Rust native core, `qdrant-client` supports Python 3.14 | **Integrate as a Dependency** | High-performance vector database with local embedded storage mode (`QdrantClient(path="data/qdrant")`). Backs SEED's episodic and semantic memory alongside SQLite without requiring an external cloud server. |
| **G. Piper** | `github.com/rhasspy/piper` | MIT | Standalone C++ binary (`piper.exe`) on Windows | **Integrate as a Dependency (CLI Tool)** | Fast, local neural TTS with Arabic (`ar_JO-kareem`) and English voices. Note: original repo was archived October 2025 (moved to OHF-Voice). Integrate by invoking precompiled `piper.exe` via stdin/stdout pipe in a subordinate SEED TTS worker. |
| **H. LocalVoiceAgent** | `github.com/Soumodeep-Ganguly/...` | **NO LICENSE** (Unlicensed / All Rights Reserved) | Python 3.10-3.12, Windows 10/11 | **Use as Architectural Reference Only** | Lacks an open-source license, presenting severe legal copyright risk if code is copied. However, its architecture (CPU-only int8 Whisper, Kokoro ONNX, PySide6 floating orb, Start-menu-safe global hotkeys) serves as a valuable implementation reference for SEED. |
| **I. Jarvis** | `github.com/brocode47/jarvis` | Apache-2.0 | Python 3.10-3.12, Windows 10/11 | **Adapt Selected Components** | Fully local Windows voice assistant. Adapt its Windows Start Menu / `shell:AppsFolder` application discovery routine, DPAPI credential encryption helper, and two-tier deep research (planner/worker) breakdown. |

---

## 2. In-Depth Candidate Evaluations

### Candidate A: Dodaios (`Dodaios/Dodaios`)
- **Repository Structure:** Monorepo containing `dodaios/` (Python core), `ui/` (Electron / TypeScript frontend), `conductor/`, `board-backend/`, and `tools/`.
- **License:** Apache-2.0 (relicensed from MIT at v1.6.0). Safe for enterprise and local integration.
- **Windows Support & Requirements:** Native Windows support via `install.ps1`, PowerShell scripts, and PyInstaller bundling.
- **Python Compatibility:** Tested on Python 3.10 - 3.12 with `uv` lockfile. Not verified on Python 3.14.
- **Maintenance & Community:** Very active (v5.0.0 released November 2026, 361 stars, 23 contributors).
- **Security & Authorization Model:** Features a 4-tier risk classification: `safe`, `monitor`, `ask`, and `block`. Uses Claude Code and Codex harnesses.
- **Integration Strategy:** **Use as an architectural reference only.** SEED already possesses a superior, cryptographically validated permission and approval architecture (`PermissionEngine`, `ApprovalManager`). SEED should study Dodaios's multi-pane agent coordination and subagent brief-writing patterns while keeping SEED as the sole composition root.

### Candidate B: RealtimeSTT (`KoljaB/RealtimeSTT`)
- **Repository Structure:** Python library in `RealtimeSTT/`, plus `RealtimeSTT_server/` (packaged FastAPI WebSocket/HTTP production server).
- **License:** Apache-2.0 (v1.2.0 relicensed from MIT).
- **Windows Support & Requirements:** Full Windows support using WASAPI / PortAudio and CTranslate2 / ONNX Runtime.
- **Python Compatibility Risk:** **High in Python 3.14.** RealtimeSTT explicitly states in its documentation: *"The current CI matrix covers Python 3.11 and 3.12. Python 3.13 and newer are not release targets until dependency and CI gates are available."* PyAudio and CTranslate2 do not provide prebuilt wheels for Python 3.14 on Windows.
- **Maintenance & Community:** Extremely active (v1.2.0 released November 2026, 10.2k stars, 29 contributors).
- **Resource Footprint:**
  - Fast pause transcript (`live-flush Preview` via `nemotron_ort`): ~48 ms latency on CPU.
  - Final transcript: ~149 ms via tail-anchored `faster_whisper` or Parakeet.
  - Memory: ~500 MB RAM for int8 models; 0 MB VRAM on CPU.
- **Integration Strategy:** **Isolated Subprocess / Daemon Integration.** Do not attempt to pip install into SEED's `.venv` (Python 3.14). Instead, run the packaged `stt-server-production` inside a lightweight Python 3.11/3.12 helper venv or standalone executable, binding exclusively to `127.0.0.1:8010`. Implement SEED's `SpeechInputAdapter` in `interfaces/media.py` to connect to this loopback WebSocket.

### Candidate C: Mem0 (`mem0ai/mem0`)
- **Repository Structure:** `mem0/` (Python core), `mem0-ts/`, `server/` (Docker self-hosted), `cli/`.
- **License:** Apache-2.0.
- **Windows Support & Requirements:** Cross-platform; works on Windows with SQLite or local vector databases.
- **Python Compatibility:** Python 3.10 - 3.12. Heavy dependency tree (`pydantic`, `openai`, `qdrant-client`, `spacy`).
- **Maintenance & Community:** High activity (68.8k stars, 414 contributors). Major algorithm revision in April 2026 introducing single-pass ADD-only extraction, entity linking, and temporal reasoning.
- **Security & Authorization Model:** In standard Mem0, memory extraction runs automatically without governance. In SEED, user preferences and persistent memories require human approval if marked sensitive.
- **Integration Strategy:** **Adapt Selected Components.** Do not import the bloated `mem0ai` package. Instead, adapt Mem0's:
  1. *Prompt templates for structured fact and entity extraction*.
  2. *Entity linking across memories*.
  3. *Hybrid retrieval scoring formula* ($Score = \alpha \cdot Semantic + \beta \cdot BM25 + \gamma \cdot Entity$).
  Implement this logic directly into SEED's `memory/store.py`, leveraging the existing `memory_items` table and Qdrant.

### Candidate D: Playwright Python (`microsoft/playwright-python`)
- **Repository Structure:** Official Microsoft Python client communicating with a Node-based driver.
- **License:** Apache-2.0.
- **Windows Support & Requirements:** First-class Windows support (Chromium, Firefox, WebKit, and MS Edge).
- **Python Compatibility:** Fully compatible with Python 3.8 - 3.14.
- **Maintenance & Community:** Premier enterprise maintenance (v1.65.1 released November 2026, 15.1k stars, 66 contributors).
- **Security & Governance:** Browser automation carries critical SSRF, credential theft, and unintended purchase risks.
- **Integration Strategy:** **Integrate as a Dependency.** Install `playwright` into `.venv`. Register governed SEED tools:
  - `browser.navigate(url)`: Read action, checks domain allowlist.
  - `browser.snapshot()`: Read action, captures DOM tree / screenshot for multimodal models.
  - `browser.click(selector)` / `browser.type(selector, text)`: Write actions, **require human approval** if targeting external transactional sites.

### Candidate E: Silero VAD (`snakers4/silero-vad`)
- **Repository Structure:** Minimal Python package with pre-trained ONNX and PyTorch JIT models.
- **License:** MIT License.
- **Windows Support & Requirements:** Runs anywhere ONNX Runtime runs; minimal CPU footprint (<1 ms per 30 ms chunk, ~2 MB model size).
- **Python Compatibility:** Python 3.8 - 3.14 using `onnxruntime`.
- **Maintenance & Community:** Highly maintained (v6.2.3 released, 10.6k stars).
- **Integration Strategy:** **Integrate as a Dependency.** Use `onnxruntime` to run `silero_vad.onnx` directly in SEED's audio worker thread. Emits `SPEECH_STARTED` and `SPEECH_ENDED` events into SEED's event loop. When speech starts during assistant playback, SEED immediately triggers `SpeechOutputAdapter.interrupt()`.

### Candidate F: Qdrant (`qdrant/qdrant`)
- **Repository Structure:** High-performance vector search engine written in Rust with official Python client `qdrant-client`.
- **License:** Apache-2.0.
- **Windows Support & Requirements:** Prebuilt Windows binaries; Python client supports local in-process directory storage (`path="D:/SEED-AI/data/qdrant"`).
- **Python Compatibility:** Python 3.8 - 3.14.
- **Maintenance & Community:** High enterprise maintenance (v1.20.0, 35.5k stars).
- **Resource Footprint:** Extremely efficient; vector quantization cuts RAM usage by up to 97%.
- **Integration Strategy:** **Integrate as a Dependency.** Add `qdrant-client` to `.venv`. Use embedded disk storage (`QdrantClient(path="D:/SEED-AI/data/qdrant")`) to index session dialogue and long-term memory embeddings. Works alongside SQLite (`data/seed_memory.db`) which retains strict relational authority for tasks, approvals, and events.

### Candidate G: Piper (`rhasspy/piper`)
- **Repository Structure:** C++ core using ONNX Runtime with Python training scripts and voices repository.
- **License:** MIT License.
- **Status Notice:** Original repository `rhasspy/piper` was **archived by its owner on Oct 6, 2025**. Active development transitioned to Open Home Foundation (`OHF-Voice/piper1-gpl`).
- **Windows Support & Requirements:** Standalone prebuilt Windows binary (`piper.exe`) runs on CPU with zero Python dependency issues.
- **Language Support:** Excellent English models (`en_US-lessac`, `en_GB-alan`) and Arabic models (`ar_JO-kareem-low`, `ar_JO-kareem-medium`).
- **Integration Strategy:** **Integrate as External Executable.** Download precompiled Windows `piper.exe` and voice models into `D:\SEED-AI\bin\piper\`. Wrap execution inside `SpeechOutputAdapter.synthesize()`: stream text via stdin, receive raw PCM via stdout, and route to Windows audio playback (`waveOut` / `sounddevice`).

### Candidate H: LocalVoiceAgent (`Soumodeep-Ganguly/...`)
- **Repository Structure:** Standalone Python Windows voice assistant (`app/`, `audio/`, `stt/`, `vad/`, `tts/`, `ollama/`, `tools/`, `ui/`).
- **License Risk:** **CRITICAL RISK — NO LICENSE FILE.** Under standard copyright law, an unlicensed repository is "All Rights Reserved". Directly copying source code creates legal and IP liability.
- **Architecture Highlights:** Designed specifically for low-resource Windows CPUs (Intel Core i7, 16 GB RAM):
  - Sequential model residency: Whisper, Ollama, and Kokoro are unloaded so only one model resides in RAM at a time.
  - Global hotkeys (`Ctrl+Win` push-to-talk, `Ctrl+Win+Space` auto-stop) using `pynput` with Start menu suppression.
  - Lightweight PySide6 floating orb showing assistant states.
- **Integration Strategy:** **Use as an Architectural Reference Only.** Do not copy source files. Re-implement the clean concepts in SEED:
  1. *Global Windows Hotkey Manager* via `ctypes.windll.user32.RegisterHotKey` (avoiding `pynput` keyboard hook issues).
  2. *Low-Resource Model Residency Manager* in `brain/model_gateway.py` (explicit Ollama unload before running heavy local tools).

### Candidate I: Jarvis (`brocode47/jarvis`)
- **Repository Structure:** Python Windows assistant forked from `onlyflames360/jarvis` / `ndunl075/Jarvis`.
- **License:** Apache-2.0.
- **Windows Support & Requirements:** Native Windows application using PyInstaller, `shell:AppsFolder`, and Windows DPAPI.
- **Python Compatibility:** Python 3.10 - 3.12.
- **Standout Features:**
  - Start menu and Microsoft Store app launching via `shell:AppsFolder` URIs.
  - Windows DPAPI credential encryption (`CryptProtectData` / `CryptUnprotectData`).
  - Two-tier deep research planner/worker decomposition.
- **Integration Strategy:** **Adapt Selected Components.**
  1. *Windows DPAPI Credential Store:* Adapt DPAPI ctypes routines into `security/credentials.py` to encrypt optional API keys (OmniRoute, Brave) at rest.
  2. *Windows Application Indexer:* Adapt `shell:AppsFolder` enumeration into a new registered SEED tool (`windows.launch_app`) subject to explicit permission allowlists.

---

## 3. Supplementary & Superior Alternatives

| Capability Needed | Evaluated Candidate | Superior / Better-Maintained Alternative | Why the Alternative is Superior |
|---|---|---|---|
| **Wake-Word Detection** | RealtimeSTT (Porcupine / OpenWakeWord) | **`openWakeWord` (v0.6.0+)** | Pure Apache-2.0, ONNX-based, runs locally on CPU without proprietary vendor keys (unlike Picovoice Porcupine), easily trained for custom phrases like "Hey SEED". |
| **Arabic & English TTS** | Piper (Archived October 2025) | **`Kokoro-ONNX`** or **`Sherpa-ONNX TTS`** | Kokoro-ONNX provides state-of-the-art voice naturalness (82M parameters, Apache-2.0) running entirely in ONNX Runtime CPU. For Arabic, Sherpa-ONNX actively maintains VITS/Matcha models with active 2026 commits. |
| **Windows UI Automation** | Jarvis (basic app open) | **`pywin32` / `UIAutomationCore`** | `pywin32` is already installed in SEED's `.venv` (version 312). Using native Microsoft UI Automation allows inspecting window titles, focusing apps, and sending accessibility events safely without brittle pixel automation. |
| **Local Text Embeddings** | Mem0 default (OpenAI API) | **`bge-m3` or `gte-Qwen2-1.5B` via FastEmbed/Ollama** | Fully local, multilingual (superb Arabic and English vector representation), runs locally on CPU or via Ollama `/api/embeddings`. |

---

## 4. Priority Capabilities Mapping to Open-Source Strategies

| Priority Capability | Strategy & Integration Pattern | Primary Source Component / Tool | Governing SEED Policy |
|---|---|---|---|
| **1. Reliable Tool Calling & Bounded Loops** | Core SEED Architecture (Preserve) | `SeedOrchestrator` + `ToolRegistry` | Step budget (8 max), strict JSON schema, timeout, argument digestion. |
| **2. Windows System Control** | Adapt Jarvis / pywin32 | Win32 ctypes + `pywin32` (installed in `.venv`) | Read actions (`system.health`, `windows.list_windows`) allowed; `windows.launch_app`, `windows.close_process` require permission checks & confirmation. |
| **3. Browser Automation** | Integrate Playwright Python | `playwright` via SEED `browser.*` tools | Default-deny; restricted to allowlisted domains; form submits and downloads require human approval. |
| **4. Persistent Multi-Level Memory** | Integrate Qdrant + Adapt Mem0 | Embedded Qdrant (`qdrant-client`) + `memory_items` SQLite | User preferences require explicit approval before persistence; sensitive data redaction on write. |
| **5. VAD & Streaming STT** | Integrate Silero VAD + RealtimeSTT Daemon | Silero VAD (ONNX) + RealtimeSTT loopback WebSocket | Raw audio is never stored by default; microphone has visible indicator. |
| **6. "Hey SEED" Wake Word** | Integrate openWakeWord | `openWakeWord` ONNX runtime | Off by default; requires explicit privacy acknowledgement in `WakeWordPolicy`. |
| **7. Arabic & English Speech Recognition** | RealtimeSTT / faster-whisper | Multilingual Whisper INT8 (`whisper-small` / Parakeet) | Transcriptions enter `SeedApplication.seed_request()` identically to typed text. |
| **8. Arabic & English Text-to-Speech** | Integrate Piper CLI / Kokoro-ONNX | `piper.exe` (`ar_JO-kareem`, `en_GB-alan`) | Synthesizes response from SEED turn; pauses or cancels instantly on interruption. |
| **9. Barge-in & Low-Latency Interruption** | Adapt Silero VAD + Event Hook | SEED `AssistantState` state machine | On VAD speech trigger, emit cancellation to TTS audio player and mark session interrupted. |
| **10. Screen & Document Understanding** | Integrate Win32 GDI + Ollama Vision | `windows.capture_screen` + Ollama `qwen2.5-vl` | Screenshots saved only to temporary memory; explicit approval required for continuous capture. |
| **11. MCP & Reusable Skills** | Preserve SEED MCP Server | `interfaces/seed_mcp_server.py` (MCP SDK 2.3.0) | MCP clients must call `seed_request`; low-level tools cannot bypass orchestrator. |
| **12. Background Tasks & Proactive Monitor** | Adapt Windows Task Scheduler + Cron Engine | Lightweight Python APScheduler / Win32 Task | Scheduled tasks run with fixed caller identity; cannot escalate privileges. |
| **13. Multi-Agent Delegation** | Reference Dodaios / SEED Orchestrator | Subagent execution under SEED supervisor | Subagents execute in isolated sandbox sessions; all tool calls bubble to SEED policy engine. |
| **14. Desktop, Tray, Orb & Avatar Integration** | Preserve Desktop Server + PySide6 Reference | Web Smart Orb (`desktop/app.js`) + Win32 system tray | Presentation clients display state only; cannot issue tool executions or bypass CSRF/Host checks. |

---

## 5. Security & Isolation Boundaries for External Code

To prevent external repositories from compromising SEED's security:

1. **Zero External Permission Authorities:**
   - Under no circumstances will Dodaios, Mem0, or Jarvis permission code replace `security/permission_engine.py`.
   - Every tool call proposed by any model or subagent must pass SEED's `check(action, tool, scope, identity)`.
2. **Subordinate Process Isolation:**
   - RealtimeSTT, Piper, and Playwright operate strictly as subprocesses or background services.
   - If a helper process crashes or is hijacked, it has no direct database access, cannot read SEED encryption keys, and cannot execute shell commands.
3. **Loopback & Credential Safety:**
   - All inter-process communication (FastAPI STT server, Desktop control center, Ollama) binds strictly to `127.0.0.1`.
   - Credentials (e.g., OmniRoute keys) are encrypted using Windows DPAPI and decrypted only in-memory at request time.
