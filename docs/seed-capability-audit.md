# SEED-AI Capability Completion & System Audit

**Audit Date:** 2026-11-12
**Target Environment:** Windows 11 (64-bit), Python 3.14.4 (`.venv`)
**Project Root:** `D:\SEED-AI`
**Evaluation Scope:** Codebase inspection, live runtime probing, dependency analysis, database examination, system integration audit.

---

## Executive Summary

SEED-AI is architected as a local-first, highly governed personal AI operating assistant for Windows. Unlike open-source wrappers that hand control over to unconstrained agent loops or external cloud platforms, SEED strictly enforces that the central core owns task orchestration, policy decisions, granular permissions, approval workflows, memory persistence, and audit logging.

The codebase exhibits rigorous software engineering patterns:
- **Clean composition root** (`SeedApplication.seed_request()`)
- **Strict default-deny authorization** (`PermissionEngine`)
- **Single-use, time-bound, parameter-digested approvals** (`ApprovalManager`)
- **Reentrant-safe idempotency guard** (`IdempotencyGuard`)
- **Path-traversal and symlink-proof workspace isolation** (`WorkspaceGuard`)
- **Secure loopback-only presentation server** (`SeedDesktopHTTPServer`)
- **Deterministic 70-test suite** running under Python 3.14.4 (66 passed, 4 skipped solely due to live model availability)

However, SEED is currently in an early architectural stage where only **two** tools are registered (`workspace.list` and `system.health`), media adapters are pure abstract contracts without active audio/video runtimes, tasks submitted by lower-level calls remain permanently in `pending` status without a recovery loop, and the background Ollama service is disconnected from the model store in `D:\AI\Models`.

---

## 1. Verified Architecture & Preserved Core Components

The following existing modules are well-engineered, verified by tests, and **must be preserved** as the central foundation:

| Module / Component | File Location | Architectural Responsibility | Preservation Rationale |
|---|---|---|---|
| `SeedApplication` | `core/application.py` | Unified application composition root and entry point (`seed_request()`). | Connects orchestrator, tools, permissions, task engine, operations, and MCP adapter. |
| `SeedOrchestrator` | `core/orchestrator.py` | Bounded multi-step turn coordinator, context retrieval, tool execution, retry gating, and approval resumption. | Strictly enforces step budgets (max 8 steps, 16 tool calls), time limits (120s), and cancellation tokens. |
| `ModelGateway` | `brain/model_gateway.py` | Provider abstraction and model capability gate. | Auto-discovers tool support; prevents tools from being sent to models lacking advertised capability. |
| `OllamaProvider` | `brain/providers/ollama.py` | Native Ollama REST API client (`/api/chat`, `/api/tags`, `/api/show`). | Local-first default provider; handles tool call parsing and execution stats. |
| `OmniRouteProvider` | `brain/providers/omniroute.py` | OpenAI-compatible router client (`/v1/chat/completions`). | Secure optional cloud/gateway routing with DPAPI/callback credential injection. |
| `PermissionEngine` | `security/permission_engine.py` | Policy enforcement authority with granular per-tool, per-action, per-scope checks. | Enforces default-deny; flags destructive operations (`write`, `delete`, `execute`, `deploy`, `modify`). |
| `ApprovalManager` | `security/approval_manager.py` | Cryptographically digested approval requests with TTL expiration. | Prevents replay attacks, binds approvals to exact argument digests, and supports SQLite persistence. |
| `IdempotencyGuard` | `security/idempotency.py` | Deduplication and conflict prevention for tool executions. | Caches completed results, tracks in-flight keys, and protects against reentrant duplicate execution. |
| `WorkspaceGuard` | `runtime/workspace_guard.py` | Strict filesystem perimeter validation. | Enforces workspace rooting, blocks absolute paths, blocks `..` traversals, and denies symlinks. |
| `ToolRegistry` | `core/tool_registry.py` | Schema-validated tool registry with strict JSON schema checking. | Validates arguments before authorization or execution; enforces `additionalProperties: false`. |
| `MemoryStore` | `memory/store.py` | Multi-table SQLite repository with connection safety (`ClosingConnection`). | Manages tasks, events, sessions, session messages, typed memory items, approvals, and idempotency. |
| `DesktopServer` | `interfaces/desktop_server.py` | Loopback HTTP and SSE server with CSRF, Host validation, and security headers. | Completely isolated, non-probing status API, sanitized event stream omitting sensitive payload data. |
| `MCP Adapter & Server` | `interfaces/tool_adapter.py`, `interfaces/seed_mcp_server.py` | MCP standard protocol interface exposing `seed_request` and `workspace_list`. | Conforms to official MCP SDK 2.3.0 on Python 3.14.4. |

---

## 2. Deep Audit of Current Implementation

### 2.1 Python Environment & Python 3.14.4 Compatibility
- **System Environment:**
  - System PATH default python is `Python 3.7.7` (legacy system install).
  - Windows Python Launcher (`py`) lists:
    - `-V:3.14[-64] * Python 3.14.4` (active 64-bit runtime).
    - `-V:3.12 Python 3.12 (64-bit)` (broken path `C:\ZKBioTime\python3128\python.exe`).
- **Project Virtual Environment (`D:\SEED-AI\.venv`):**
  - Python version: `Python 3.14.4`.
  - Installed packages: `mcp 2.3.0`, `mcp-types 2.3.0`, `pydantic 2.14.3`, `pydantic_core 2.50.4`, `starlette 1.10.0`, `uvicorn 0.54.0`, `pywin32 312`, `jsonschema 4.26.0`, `anyio 4.16.0`, `cffi 2.1.1`, `cryptography 50.0.2`, `truststore 0.10.5`.
  - **Compatibility Assessment:**
    - Standard library modules in Python 3.14 (such as `sqlite3`, `ctypes`, `http.server`, `urllib.request`, `concurrent.futures`, `dataclasses`, `enum`) operate without any syntax or runtime warnings.
    - However, many popular heavy machine learning packages (e.g., PyTorch, CTranslate2, faster-whisper, onnxruntime prebuilt wheels) currently lack official binary wheels for Python 3.14.4 on Windows.
    - **Architectural Directive:** Audio capture, STT, and heavy vector embeddings must either use pure ONNX Runtime CPU if compatible wheels exist, run in an isolated Python 3.11/3.12 helper subprocess, or interface via a localhost daemon (e.g., RealtimeSTT production server on port 8010).

### 2.2 Test Suite Execution & Coverage
- **Command:** `& "D:\SEED-AI\.venv\Scripts\python.exe" -m unittest discover tests -v`
- **Results:**
  - **Total Tests:** 70
  - **Passing:** 66
  - **Skipped:** 4
  - **Failures / Errors:** 0
  - **Execution Time:** ~6.75 seconds
- **Skipped Tests Analysis (`tests/test_live_ollama_integration.py`):**
  - `test_authorized_health_tool_round_trips_through_permissions` (skipped)
  - `test_streaming_is_not_advertised_and_requests_are_not_streamed` (skipped)
  - `test_text_request_uses_qwen_through_seed_application` (skipped)
  - `test_unregistered_tool_is_denied_and_not_executed` (skipped)
  - **Root Cause:** These tests require a live Ollama endpoint with `qwen3:4b` installed. While Ollama's HTTP server is running on `http://127.0.0.1:11434`, its returned model list was empty (`{"models":[]}`).

### 2.3 Git Repository & Source Control Status
- **Branch:** `main`
- **Commit History:** `fatal: your current branch 'main' does not have any commits yet`. The repository is newly initialized without an initial commit.
- **Staged Files:** 46 files staged (`brain/`, `core/`, `interfaces/`, `memory/`, `runtime/`, `security/`, `desktop/`, `tests/`, `docs/`).
- **Unstaged Modified:** `.vscode/settings.json` (modified).
- **Untracked Files:** `tests/test_live_ollama_integration.py`.

### 2.4 Database Schema & State Audit (`data/seed_memory.db`)
- **Database Engine:** SQLite 3 with WAL support and `PRAGMA foreign_keys = ON`.
- **Existing Tables:**
  1. `tasks`: Tracks command string, execution status, and timestamps.
  2. `events`: Append-only audit trail linking task IDs to event types and sanitized details.
  3. `memory`: Key-value text storage for basic memory items.
  4. `sessions`: Multi-session management with `session_id`, `title`, and `project_id`.
  5. `session_messages`: Structured dialogue history storing `role` and `message_json`.
  6. `session_tasks`: Junction table mapping sessions to task executions.
  7. `memory_items`: Categorized memory store (`durable_knowledge`, `user_preference`, `project_context`, `temporary_context`) with approval status, project scoping, and expiration dates (`expires_at`).
  8. `approval_requests`: Human approval lifecycle records storing identity digests, arguments digests, status, and expiration.
  9. `idempotency_records`: Operation deduplication records storing status, fingerprint, and cached result JSON.
- **Data State Inspection:**
  - Tasks row count: **11**
  - Events row count: **18**
  - **Critical Finding:** All 11 tasks in the database have `status = 'pending'`.
  - In `runtime/agent_runtime.py`, `list_workspace()` calls `self.tasks.submit()`, inserts an event, but never executes `self.tasks.set_status(task_id, "completed")`. Lower-level tools bypassed status completion.

### 2.5 Task Lifecycle & Recovery Mechanism
- `core/task_engine.py` provides:
  - `submit(command)` -> creates task in `pending` state.
  - `set_status(task_id, status)` -> updates status and completion timestamp.
  - `record_event(task_id, event_type, details)` -> records audit log.
- **Defects Identified:**
  - **No Startup Recovery:** If the SEED process exits or crashes while tasks are `running` or `pending`, there is no startup reconciliation loop to identify orphaned tasks, mark them `interrupted` or `failed`, or resume them.
  - **No Active Worker Queue:** Tasks are executed inline during `orchestrator.run()`. There is no background worker or asynchronous queue for scheduled or long-running tasks.

### 2.6 Windows Startup & System Integration
- **Windows Scheduled Task:**
  - **Task Name:** `SEED-AI`
  - **State:** `Ready`
  - **Trigger:** `MSFT_TaskLogonTrigger` (executes automatically upon user logon).
  - **Action Executed:** `D:\SEED-AI\.venv\Scripts\python.exe -B -m interfaces.desktop_server --port 8765`
  - **Working Directory:** `D:\SEED-AI`
- **Assessment:**
  - Auto-start is configured for the desktop HTTP server.
  - However, no system tray icon, background daemon, or Windows Service exists to manage graceful restarts, audio device watchers, or process health.

### 2.7 Ollama Configuration & Local Model Path Discrepancy
- **Ollama CLI Version:** `0.40.16`
- **Environment Configuration:**
  - User/System Environment Variable: `OLLAMA_MODELS = D:\AI\Models`
- **Physical Model Storage Inspection (`D:\AI\Models`):**
  - `D:\AI\Models\blobs`: Contains 6 model blobs, including a 2.50 GB file (`sha256-3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f`) representing `qwen3:4b`.
  - `D:\AI\Models\manifests\registry.ollama.ai\library\qwen3\4b`: Manifest exists (1,022 bytes).
  - `D:\AI\Models\manifests-v2\ollama.com\library\qwen3\4b`: Manifest-v2 exists (859 bytes).
- **Active Process Inspection:**
  - Process ID: `3132` (`C:\Users\ahmed\AppData\Local\Programs\Ollama\ollama.exe serve`)
  - Process ID: `21136` (`ollama app.exe`)
- **The Discrepancy:**
  - Running `curl http://127.0.0.1:11434/api/tags` returns `{"models":[]}`.
  - The currently running Ollama service process was launched before `OLLAMA_MODELS` was added or inherited, so it reads from `C:\Users\ahmed\.ollama\models` (which has no completed models).
  - The model `qwen3:4b` is physically downloaded and ready on `D:\AI\Models`. Once the Ollama service is restarted with its environment pointing to `D:\AI\Models`, the live model will immediately be discovered and the 4 skipped integration tests will pass.

### 2.8 Desktop Endpoints & Frontend Control Center
- **Server:** `SeedDesktopHTTPServer` in `interfaces/desktop_server.py`.
- **Port:** Loopback `127.0.0.1:8765`.
- **Implemented Endpoints:**
  - `GET /`: Serves `desktop/index.html` with injected CSRF token.
  - `GET /styles.css`: Serves CSS stylesheet.
  - `GET /app.js`: Serves client-side JavaScript.
  - `GET /api/status`: Returns non-probing cached service status.
  - `GET /api/history`: Returns paginated task execution history.
  - `GET /api/audit`: Returns sanitized audit events.
  - `GET /api/approvals`: Returns pending human approval requests.
  - `GET /api/sessions/{session_id}`: Returns visible user/assistant session chat messages.
  - `GET /api/events`: Server-Sent Events (SSE) stream providing real-time UI updates.
  - `POST /api/request`: Accepts `{request, session_id, approval_id}`, routes to `SeedApplication.seed_request()`.
  - `POST /api/approvals/approve`: Accepts `{approval_id, request, session_id}`, approves and resumes.
- **Frontend Capabilities (`desktop/app.js`):**
  - Smart Orb presentation supporting states: `idle`, `listening`, `processing`, `responding`, `executing`, `awaiting_approval`, `error`.
  - Dynamic status tabs: Assistant Feed, Task History, Approvals Queue, Audit Log, Settings.
  - Same-origin and `X-SEED-CSRF` header enforcement.
- **Limitations:**
  - Model response streaming is not supported (HTTP response is returned only after the complete turn finishes).
  - No voice input/output controls in the UI.
  - No tray minimize or floating overlay widget.

---

## 3. Currently Implemented vs. Missing Capabilities

| Capability Domain | Implemented in SEED | Missing / Incomplete in SEED |
|---|---|---|
| **1. Agent Execution & Orchestration** | • `SeedOrchestrator` multi-step turn loop (max 8 steps)<br>• Strict budget limits & cancellation tokens<br>• `SeedApplication.seed_request()` composition root | • Subagent delegation under SEED supervision<br>• Streaming model token generation<br>• Dynamic prompt assembly from skill manifests |
| **2. Tool Ecosystem** | • Strict JSON schema validation (`ToolDefinition`)<br>• Parallel-safe read execution<br>• Only 2 tools registered: `workspace.list`, `system.health` | • File read / write / edit tools<br>• Shell / command execution tools (under approval)<br>• Process management tools<br>• Window and display control |
| **3. Windows System Control** | • Read-only memory, CPU, and disk metrics (`system.health`) via Win32 ctypes | • Start menu / `shell:AppsFolder` app launching<br>• Window focus, minimize, maximize<br>• Clipboard read / write / history<br>• Global hotkey handling (PTT, pause, cancel)<br>• System audio volume / mute control |
| **4. Browser Automation** | • None | • Playwright integration wrapped in SEED tools<br>• Page navigation, snapshot, click, form fill<br>• Domain allowlisting and destructive action approval |
| **5. Memory & Persistence** | • Relational SQLite schema for tasks, events, sessions, approvals, idempotency<br>• Categorized `memory_items` table with approval requirement for user preferences | • Vector semantic search (Qdrant / embeddings)<br>• Temporal reasoning & automated fact extraction<br>• Automated memory decay and compaction |
| **6. Voice & Speech (STT/VAD)** | • Interface contracts in `interfaces/media.py` (`SpeechTranscript`, `SpeechInputAdapter`, `WakeWordPolicy`) | • Microphone capture audio pipeline<br>• Silero VAD voice activity detection<br>• Offline streaming Whisper STT (Arabic & English)<br>• "Hey SEED" wake-word detection<br>• Low-latency barge-in interruption |
| **7. Speech Synthesis (TTS)** | • Interface contracts in `interfaces/media.py` (`SpeechRequest`, `SpeechAudio`, `SpeechOutputAdapter`) | • Local TTS engine (Piper / Kokoro-ONNX)<br>• Arabic (`ar_JO`) and English voice models<br>• Audio playback queue with instant interruption |
| **8. Visual & Multimodal** | • Presentation state contract (`VisualStateUpdate`, `VisemeFrame`)<br>• Web-based Smart Orb CSS animation | • Screenshot capture and window cropping tool<br>• Multimodal vision model routing (e.g. LLaVA / Qwen-VL)<br>• 3D avatar rendering / lip-sync engine |
| **9. Security & Governance** | • Default-deny permission engine<br>• Time-bound argument-digested approvals<br>• Replay & idempotency guards<br>• Strict workspace path & symlink guard | • Windows DPAPI credential encryption at rest<br>• Per-tool outbound network egress firewall<br>• Clipboard secret filtering |
| **10. Background Automation** | • Windows Scheduled Task for startup on logon | • In-process cron / background scheduler<br>• Proactive monitoring & notifications<br>• Orphaned task recovery upon process restart |

---

## 4. Defects & Incomplete Behaviors Identified

1. **Pending Task State Drift:**
   - Tasks submitted via `AgentRuntime.list_workspace` or `TaskEngine.submit` remain in `pending` status indefinitely because status update calls (`set_status(task_id, "completed")`) were omitted in non-orchestrator execution paths.
2. **Absence of Orphaned Task Recovery:**
   - If the application server restarts while tasks are `running` or `pending`, no reconcile loop runs to update their status.
3. **Disconnected Ollama Model Path:**
   - The active Ollama process (PID 3132) does not see the 2.5 GB `qwen3:4b` model in `D:\AI\Models` because it was started without the `OLLAMA_MODELS` environment variable loaded into its process block.
4. **Tool Ecosystem Starvation:**
   - With only `workspace.list` and `system.health`, SEED cannot read file contents, modify files, launch applications, or interact with Windows, severely limiting practical agent utility until safe, governed tools are added.
5. **Media Layer Inactivity:**
   - `interfaces/media.py` provides interfaces, but there is zero concrete audio code, preventing any hands-free or companion voice usage.
6. **No API Token Streaming:**
   - `interfaces/desktop_server.py` blocks synchronously during `SeedApplication.seed_request()`, meaning long LLM turns appear frozen in the UI until completion.

---

## 5. Security & Isolation Verification

SEED's core security invariants were inspected and verified against the threat model:

1. **No External Bypasses:**
   - All client entry points (`interfaces/desktop_server.py`, `interfaces/seed_mcp_server.py`) route exclusively through `SeedApplication.seed_request()` or `SeedApplication.tool_adapter.invoke()`.
   - No external model, client, or tool can execute code without passing `PermissionEngine.check()`.
2. **Workspace Boundary:**
   - `runtime/workspace_guard.py` resolves canonical paths, forbids absolute paths outside workspace, rejects `..` traversals, and denies symbolic links. Verified by unit tests.
3. **Approval Integrity:**
   - Approvals are bound to `hashlib.sha256(json.dumps(arguments))` and `hashlib.sha256(json.dumps(identity))`. If an attacker or compromised model alters a single parameter, the approval is rejected.
   - Approvals expire after TTL (default 300 seconds) and are marked `consumed` upon first use (replay protection).
4. **Idempotency Protection:**
   - High-impact operations use `IdempotencyGuard` to prevent double-execution of identical requests.

---

## 6. Recommendations for Architecture Preservation

1. **Maintain SEED Composition Root:**
   - Never replace `SeedApplication` with an external framework (e.g., LangChain, AutoGen, CrewAI, or Dodaios superagent).
2. **Preserve Subordinate Adapters:**
   - Keep STT, TTS, Browser, and Desktop interfaces strictly subordinate to SEED. They must emit events or receive instructions, never make authorization decisions.
3. **Resolve Environment Path for Ollama:**
   - Ensure the Ollama daemon runs with `OLLAMA_MODELS=D:\AI\Models` so local offline inference functions immediately.
4. **Introduce Core Reconcile Loop:**
   - Add a lightweight startup recovery function in `core/task_engine.py` to reconcile orphaned pending/running tasks upon launch.
5. **Expand Tool Registry Incrementally:**
   - Register atomic, typed tools (`file.read`, `file.write`, `windows.launch_app`, `browser.navigate`) with explicit policies in `PermissionEngine`.
