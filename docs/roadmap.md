# SEED-AI Platform Evolution Roadmap

## Current Architecture Map

SEED remains the only authority for request handling, model selection, permissions, approvals, tool execution, task/session state, and audit events. Clients and providers are replaceable adapters.

| Capability | Actual implementation | Current status |
|---|---|---|
| Model gateway | `brain/model_gateway.py`, `brain/providers/ollama.py`, `brain/providers/omniroute.py` | Ollama/Qwen3:4b is the default; the local API responds but has zero installed models. OmniRoute remains opt-in and its credential is unavailable. |
| Central composition | `core/application.py`, `core/orchestrator.py` | Shared `SeedApplication.seed_request()` path exists; tested with fake providers, not live inference. |
| Task and tool contracts | `core/task_engine.py`, `core/tool_registry.py` | Registered tools include workspace listing and read-only system health; lifecycle state, schemas, budgets, cancellation, and retry gating are implemented. |
| Workspace runtime | `runtime/agent_runtime.py`, `runtime/workspace_guard.py` | Read-only workspace listing and path/symlink boundaries exist. |
| Memory and governance | `memory/store.py`, `security/` | Additive SQLite sessions/memory, approvals, idempotency, and audit records exist; legacy database remains the default unless an override is set. |
| MCP | `interfaces/seed_mcp_server.py`, `interfaces/tool_adapter.py` | Actual stdio discovery and low-risk tool use tested in the project `.venv`; user objectives use `seed_request`. |
| Desktop | `interfaces/desktop_server.py`, `desktop/` | Loopback control center, Smart Orb states, status/task/audit/approval views, and sanitized SSE implemented. No user authentication; loopback-only development use. |
| Voice and avatar | `interfaces/media.py` | Replaceable contracts and wake-word privacy gate only; no microphone, STT/TTS, avatar renderer, or lip-sync implementation. |
| Build/dependencies | No project dependency/build manifest found; `.vscode/mcp.json` exists | MCP is present in `.venv`; no packages were installed. `manifests/`, `manifests-v2/`, `sources/`, and `config/` were empty at audit time. |

Name corrections from repository inspection: the agent runtime is `runtime/agent_runtime.py`, not `core/agent_runtime.py`; the actual media contracts are `interfaces/media.py`, not `brain/media.py`. No `scripts/` directory was present.

## Prioritized Phases

### Phase 1: Audit and Integrate the Existing Offline Agent

**Status: PARTIALLY IMPLEMENTED.** The actual modules are inventoried and existing behaviors have isolated tests. The shared `SeedApplication` composition root now connects the current runtime, operations, tools, permissions, and gateway.

**Dependencies:** None.

**Acceptance:** Preserve existing task/workspace behavior; prove permission default-deny, path/symlink protection, temporary-database persistence, MCP authorization, and import-safe server construction. Continue to treat legacy hardcoded paths as defaults, not test paths.

### Phase 2: Complete the Central Runtime and Agent Loop

**Status: PARTIALLY IMPLEMENTED.** `SeedOrchestrator` handles sessions, context retrieval, structured tool calls, permission decisions, approvals, bounded execution, result recording, and final responses. `SeedApplication.seed_request()` is the common user-objective entrypoint.

**Dependencies:** Phase 1.

**Acceptance:** Use a live or deterministic provider contract; every proposal resolves through the registry and permission engine; invalid/unregistered tools never run; approvals bind exact parameters and expire; result validation and task/session/event persistence are verified. Explicitly document that synchronous tool handlers cannot be forcibly interrupted.

### Phase 3: Reliable Offline Model and Tool Execution

**Status: IMPLEMENTED BUT NOT LIVE-VERIFIED.** Ollama/Qwen3:4b is the default local route; model discovery, capability checks, and endpoint/model/provider overrides exist. The local Ollama endpoint was unreachable during checks, so actual offline inference is not proven. OmniRoute remains an optional explicit provider.

**Dependencies:** Phase 2 and a running local Ollama service with a verified model.

**Acceptance:** With internet disabled, discover the installed local model, complete a harmless request, verify a response, inspect advertised tool capability, and execute a harmless registered read tool through SEED. Show that unsupported tool calling fails closed. Never silently route to a cloud provider.

### Phase 4: Real-Time Voice Runtime

**Status: PLANNED; CONTRACTS ONLY.** `interfaces/media.py` defines speech and interruption boundaries. No audio device is opened and no STT/TTS provider is active.

**Dependencies:** Phase 2; evaluate compatible local speech models/hardware. Any dependency/model download requires approval. Continuous microphone capture requires explicit user approval.

**Acceptance:** Arabic and English transcription and synthesis tested on actual hardware; local wake word is opt-in; visible mic state and mute work; partial transcription and playback are streamed; barge-in cancels playback and updates the same SEED session; privacy/recording policy is exercised. Do not claim Egyptian Arabic support until tested.

### Phase 5: Windows Device-Control Tools

**Status: PARTIALLY IMPLEMENTED.** Read-only host resource reporting is registered as `system.health` and passes through the central orchestrator and permission engine. There is no Windows process, application, audio, display, service, scheduler, or PowerShell control registered.

**Dependencies:** Phase 2 and operation-level permission/approval policies.

**Acceptance:** Add typed, schema-validated tools by risk class. Read-only system inventory is tested separately from changes. Application launch, process termination, writes, installs, power actions, and administrative work require explicit allowlists and approval. No arbitrary shell tool is exposed to models.

### Phase 6: Authorized Network and Smart-Home Integrations

**Status: PLANNED.** No network-device discovery, router, camera, Home Assistant, MQTT, Matter, or printer adapter is registered.

**Dependencies:** Phase 2, Phase 5 permission scopes, and user-provided authorized network/device profiles.

**Acceptance:** Only explicitly selected local networks/devices are contacted. Provider-specific credentials use an approved secure store. Test device health and read operations first; modifications require scoped approval. Never scan external or unauthorized networks.

### Phase 7: Skills and Connected Services

**Status: PLANNED.** The tool registry contains workspace listing and system health; there is no populated skill/service manifest catalog.

**Dependencies:** Phase 2 tool contracts, Phase 5/6 security scopes, and service credentials where required.

**Acceptance:** Every skill has ID/version, input/output schema, permissions, risk, timeout, health check, and audit contract. Integration health is backed by a real check. Service-specific tests distinguish unavailable credentials from operational success.

### Phase 8: Persistent Automation and Workflow Engine

**Status: PLANNED.** Tasks and events persist, but scheduled/recurring triggers, workflow checkpoints, and a background scheduler are absent.

**Dependencies:** Phase 2 task lifecycle, Phase 5/6 tools, cancellation/recovery semantics, and explicit ownership/scopes.

**Acceptance:** Add owner-bound, cancellable workflows with persisted checkpoints, idempotency, retry limits, run history, notifications, and approval review. Scheduled execution never inherits broader permissions than its owner granted.

### Phase 9: Memory, Events, and Monitoring

**Status: PARTIALLY IMPLEMENTED.** SQLite memory/session/task/audit APIs and a redacted local SSE feed exist. Retention/compaction policy, durable external event broker, and authenticated multi-user access are not implemented.

**Dependencies:** Phases 1–2 and the task/session schema.

**Acceptance:** Verify project/user isolation, memory corrections and retention, restart recovery, event cursor/reconnect behavior, sensitive-field redaction, and load limits using temporary databases. Do not expose internal event details to unauthorized clients.

### Phase 10: Desktop Integration and Operational Control Center

**Status: IMPLEMENTED AND VERIFIED LOCALLY; LIVE MODEL/VS CODE HOST NOT VERIFIED.** The control center is served by `interfaces/desktop_server.py` at `http://127.0.0.1:8765` during the current isolated preview. It uses `SeedApplication.seed_request()` and does not call providers directly.

**Dependencies:** Phases 1–3 server interfaces; provider live status is shown as unprobed/unavailable rather than fabricated healthy.

**Acceptance:** Chat, task/status/history, approval, and audit flows use real SEED APIs; CSRF and loopback checks reject invalid requests; SSE carries redacted state; responsive layout and reduced-motion behavior work. A separate VS Code host-session test is required before claiming VS Code acceptance. Local HTTP currently has no user login and must not bind to LAN.

### Phase 11: Avatar and Unified Voice/Visual Experience

**Status: PLANNED; PRESENTATION CONTRACTS ONLY.** Optional avatar state and viseme interfaces exist, but there is no renderer, asset, audio synchronization, or lip-sync test.

**Dependencies:** Phase 4 live voice and Phase 9 event/session lifecycle; renderer choice may require approval for heavy frameworks/assets.

**Acceptance:** Avatar receives only SEED-issued states/audio timing, supports interruption, and has no model/tool/permission authority. Verify lip sync and expressions against actual playback; otherwise keep the avatar labeled unavailable.

### Phase 12: Security Audit, Performance, and End-to-End Validation

**Status: PARTIALLY IMPLEMENTED.** Default-deny authorization, scoped approvals, idempotency, workspace guards, audit records, and local server protections have isolated coverage. Live-provider, voice, network-device, and authenticated-client acceptance remain blocked or planned.

**Dependencies:** Completed implementations of the previous applicable phases and provisioned test hardware/services.

**Acceptance:** Run the full isolated suite, provider/device/voice live tests where available, load and reconnect checks, restart recovery, project isolation, secret-redaction scan, and the twelve real-world demonstrations in the master directive. Report each as unit, integration, or live verified. No mocked result may be labeled live.

## Immediate Blockers and Approval Gates

- **Offline inference:** The Ollama 0.40.15 local API responds, but has no installed models; `qwen3:4b` is unavailable. Approve a model download before it is attempted. No model download was started.
- **Online inference:** OmniRoute `/v1/models` returned HTTP 401 because `OMNIROUTE_API_KEY` is unavailable in the SEED server process. Provide it through the approved secure process environment; do not put it in source, frontend, MCP config, or docs.
- **Voice:** Selecting/installing speech and wake-word models or enabling continuous microphone capture requires user approval.
- **Desktop security:** The development server is loopback-only but has no user authentication. Do not expose it to LAN or internet without a separately designed and tested authentication boundary.
- **Network/device control:** No authorized device profiles or credentials were available; no network discovery was run.
- **Git/build:** The workspace is not a Git repository and has no project build/dependency manifest. Do not infer clean tracked status from that absence.

## Validation Baseline

- Latest complete suite before Phase 11 changes: 65 tests passing under `D:\SEED-AI\.venv\Scripts\python.exe` on Python 3.14.4.
- Frontend syntax: `node --check desktop/app.js` passed.
- Python diagnostics: clean for modified runtime/server/media modules.
- MCP CLI: actual stdio startup, tool discovery, and authorized read-only workspace invocation passed with temporary DB/workspace.
- Desktop: loopback status, request, approval, audit, SSE, and CSRF flows passed with temporary DB/workspace and a fake model gateway.
- Live model: no successful request. Ollama API is reachable but its model inventory is empty; OmniRoute authentication remains blocked.

### Phase 11 Operational Capabilities Update

- Live diagnostics on 2026-11-11: Ollama 0.40.15 is installed and the loopback API responds with HTTP 200, but `/api/tags` returns `{"models":[]}`. Therefore `qwen3:4b` is not available and no model conversation, streaming, or live tool-call capability test can run. No model was downloaded.
- `OllamaProvider.chat()` submits `stream: false`; response-token streaming is not implemented. Tool execution is implemented only through model-proposed calls gated by provider capability metadata and SEED's `ToolRegistry`/`PermissionEngine`.
- Added `system.health`, a read-only tool for memory, processor, disk, and SEED process metrics. It is registered by `SeedApplication`, uses the existing orchestrator/permission path, and is verified via the loopback Desktop request integration test with a fake model gateway and real local OS metrics.
- Windows application control, network adapters/integrations, skills catalog, and real voice remain unimplemented; no dependencies, models, or credentials were installed or downloaded.
