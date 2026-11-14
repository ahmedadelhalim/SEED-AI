# SEED Capability Baseline

Date: 2026-11-13

Phase 4.1 update: compact planning catalog, native Ollama JSON mode, bounded repair, explicit planning timeout, plan status/resume/cancel APIs, and deterministic runtime tests were implemented. Deterministic regression count is now 116 passed; live Qwen planning was attempted again but exceeded the bounded local CPU window without a valid plan result.

This baseline distinguishes verified runtime behavior from planned or contract-only capabilities. A file or class is not treated as implemented unless an executable test or direct runtime probe supports the claim.

## Capability matrix

| Area | Current evidence | Status | Readiness | Main gap |
|---|---|---|---:|---|
| Core orchestration | `SeedApplication`, `SeedOrchestrator`, focused tests, real Qwen3 runtime request | Implemented | 85% | More complex planning and cancellation coverage |
| Persistent plan engine | `PlanEngine`, typed contract validation, durable SQLite plans/steps, dependency recovery, failure blocking, and orchestrator execution tests | Implemented/partial | 80% | Live Qwen plan generation and richer result verification |
| Model-driven planning | Planning prompt, bounded JSON repair, typed registered-tool/schema validation, cycle detection, and risk fields | Implemented/partial | 65% | Successful live Qwen JSON plan generation on local CPU and approval-aware plan generation |
| Task lifecycle | SQLite tasks, leases, transitions, orphan reconciliation, tests | Implemented | 80% | Broader crash/restart and concurrency testing |
| Memory and history | SQLite memory, sessions, search, operational history, tests | Implemented | 70% | Retention, compaction, semantic/vector retrieval |
| Model gateway/routing | Ollama and OmniRoute adapters, capability checks, timeout configuration | Implemented/partial | 75% | Provider failover and richer routing policies |
| Tool registry/execution | Typed schemas, central registry, handler execution, tests | Implemented | 85% | Versioned external integration catalog |
| Skills management | Parse, review, approval, install, digest validation, recovery tests | Implemented/partial | 70% | Dependency resolution and executable skill isolation |
| Permissions/approvals | Default deny, scope/action checks, approval binding, single-use approvals | Implemented | 90% | Trusted identity provisioning and broader policy language |
| Audit/persistence | Task, event, approval, idempotency, session persistence | Implemented | 80% | Integrity/retention controls and export |
| Workspace/file operations | Read/search/write tools with workspace and symlink guards | Implemented | 80% | More file type, size, and conflict policies |
| Desktop HTTP API | Loopback server, CSRF/same-origin, status, history, approvals, SSE | Implemented/partial | 80% | Authentication and async response streaming |
| MCP integration | Stdio MCP server and governed adapter | Implemented/partial | 75% | More transport/contract and client acceptance coverage |
| REST/HTTP integrations | Governed read-only `HttpIntegration`, registry contracts, structured errors, retries, timeout, and local tests | Implemented/partial | 55% | Auth references, rate limiting, write approval, broader protocol adapters |
| Browser automation | Design and roadmap only | Not implemented | 0% | Governed Playwright adapter with SSRF controls |
| OS administration | Read-only Windows discovery | Partial | 25% | Governed process/service/app controls |
| Agent coordination | Single central orchestrator only | Partial | 20% | Subordinate agents, delegation, aggregation |
| Retry/idempotency/recovery | Bounded provider retries, idempotency, startup task reconciliation | Implemented/partial | 70% | Fault-injection and multi-worker recovery |
| Offline operation | Ollama local path verified; external provider opt-in | Implemented/partial | 75% | Graceful no-model mode and provider health UX |
| Internet connectivity | OmniRoute adapter; no generic internet tool | Partial | 25% | Allowlisted, audited network integration |
| Arabic/English interaction | Contract and deterministic session test; Arabic model behavior not live-benchmarked | Partial | 45% | Live bilingual evaluation corpus and scoring |
| Security/privacy | Central governance, path protection, redacted SSE, no credential literals | Implemented/partial | 80% | Formal threat model, identity, secret rotation |
| Model identity | SEED contract, bilingual principles, JSONL eval cases | Partial | 40% | Automated evaluator and provenance pipeline |

## Verified benchmark suite

The reproducible benchmark is `tests/test_capability_benchmark.py` and runs with the normal test discovery command. It measures system behavior with a deterministic fake model gateway so results are attributable to SEED rather than Qwen3.

Current benchmark cases:

- `test_system_tool_selection_and_persistence`: tool selection, authorization, handler result, audit, and persistence.
- `test_unknown_tool_is_denied_without_execution`: default-deny tool boundary.
- `test_arabic_request_preserves_user_input_in_session`: bilingual input persistence and response path.

These are system benchmarks, not a claim about base-model intelligence.

## Attribution model

- **SEED-system score:** governance, routing, persistence, tool execution, denial, approval, recovery, and interface behavior.
- **Qwen3 score:** response quality, reasoning, language quality, planning, contradiction handling, and tool selection when live inference is used.
- A deterministic gateway is used for system benchmarks to prevent model variability from hiding SEED defects.

## Gap registers

### Product-critical

1. Extend the governed HTTP foundation to authenticated, rate-limited, write-approved integrations.
2. Production identity/authentication for non-local callers.
3. Connect `PlanEngine` to model-generated plans and orchestrator-owned step execution.
4. Provider failover and graceful no-model behavior.

### Security and reliability

1. Formal identity provisioning and multi-user authorization.
2. Fault-injection tests for model, database, and worker crashes.
3. Skill dependency and sandbox isolation.
4. Audit integrity, retention, and export controls.

### UX

1. Arabic/English UI localization and live bilingual acceptance.
2. Visible plan/tool timeline and richer failure recovery controls.
3. Model health and latency presentation.

### Advanced/future

1. Governed Playwright browser tools.
2. Subordinate specialist-agent delegation.
3. Vector/semantic memory.
4. LoRA/fine-tuning after provenance and evaluation gates.

## Execution order

1. Stabilize model timeout and provider health behavior.
2. Expand deterministic system benchmark and failure-injection coverage.
3. Add governed generic HTTP/REST integration primitives.
4. Add browser automation only after SSRF and approval tests exist.
5. Add agent delegation under the existing orchestrator.
6. Add semantic memory with explicit provenance and retention.
7. Build automated bilingual model evaluation.
8. Consider LoRA only after baseline regressions and data governance approval.

## Phase 4 evaluation evidence

- **Live Planning Evaluation:** Re-attempted with compact tool contracts, native Ollama JSON mode, and isolated SQLite. The request still exceeded the practical bounded local CPU execution window; no valid live plan result was recorded. The live acceptance criterion remains blocked.
- **Phase 4.1 Measurements:** Native JSON capability is now represented in `ModelRequest.response_format` and sent as Ollama `format={"type":"json"}`. Deterministic planning/API tests passed; live planning response duration exceeded the bounded 300-second evaluation window.
- **Plan Execution Evaluation:** Deterministic three-step execution passed through the central orchestrator, tool registry, permission engine, idempotency guard, result persistence, and recovery.
- **Verification Coverage:** Result verification is active for explicit criteria such as `result contains <value>` and rejects unknown criteria or unsuccessful handler results.
- **Approval UX Coverage:** Desktop and MCP plan creation/execution endpoints route through `SeedOrchestrator`; sensitive steps still require operation-bound approval. Full interactive plan-preview approval flow remains partial.
- **Resume API Coverage:** Durable plan recovery exists through `PlanEngine.resume()`; Desktop/MCP resume/cancel endpoints remain future work.
