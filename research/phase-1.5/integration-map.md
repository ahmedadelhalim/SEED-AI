# SEED-AI Integration Map (Phase 1.5)

**Document Purpose:** Traceable mapping of the central execution path through SEED-AI components.

---

## Central Execution Trace: `SeedApplication.seed_request()`

```mermaid
flowchart TD
    Client[User Interface / MCP Client / Desktop Server] --> App[SeedApplication.seed_request]
    App --> Orch[SeedOrchestrator.run]
    Orch --> Task[TaskEngine: Create & Set Running]
    Orch --> Mem[MemoryStore: Load History & Context]
    Orch --> GW[ModelGateway: Select Provider & Complete]
    GW --> Parse[Parse Tool Calls / Response]
    Parse --> Reg[ToolRegistry: Lookup Tool]
    Parse --> Val[ToolDefinition.validate_arguments]
    Val --> Perm[PermissionEngine.check]
    Perm --> Appr{Requires Approval?}
    Appr -- Yes --> ApprovalCheck[ApprovalManager.consume / Request]
    ApprovalCheck -- Denied/Pending --> Halt[Record Event & Return Status]
    ApprovalCheck -- Approved --> Exec[Execute Tool Handler with Idempotency]
    Perm -- Allow --> Exec
    Exec --> Audit[Store Task Event / Audit Log]
    Audit --> Resp[Return OrchestrationResult]
```

## Component Status Breakdown

| Transition / Component | Implementation Status | Test Coverage | Verification Method |
|---|---|---|---|
| **User Interface / MCP Adapter** | Fully Implemented | Covered | Unit tests & fake transports |
| **`SeedApplication.seed_request()`** | Fully Implemented | Covered | Integration tests |
| **`SeedOrchestrator` Loop** | Fully Implemented | Covered | Unit tests (`test_orchestrator.py`) |
| **Memory Store & Session History** | Fully Implemented | Covered | Unit tests (`test_memory_store.py`) |
| **Model Gateway (`ModelGateway`)** | Fully Implemented | Covered | Unit tests (`test_model_gateway.py`) |
| **Tool Registry & Schema Validation** | Fully Implemented | Covered | Unit tests (`test_foundation.py`) |
| **Permission Engine (`PermissionEngine`)** | Fully Implemented | Covered | Unit tests (`test_governance.py`) |
| **Approval Manager (`ApprovalManager`)** | Fully Implemented | Covered | Unit tests (`test_governance.py`) |
| **Tool Execution & Idempotency** | Fully Implemented | Covered | Unit tests (`test_governance.py`) |
| **Audit Persistence (`events` table)** | Fully Implemented | Covered | Unit tests (`test_foundation.py`) |
| **Live Model Inference & Tool Calling** | Implemented in Code | BLOCKED | Awaiting Ollama environment alignment (`OLLAMA_MODELS`) |
