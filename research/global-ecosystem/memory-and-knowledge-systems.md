# SEED-AI Memory and Knowledge Systems

**Document Purpose:** Investigation of advanced memory architectures (Letta, Mem0, Zep) and their integration into SEED-AI's SQLite persistence model.

---

## 1. Industry Memory Frameworks
- **Letta / MemGPT:** Paged core memory and archival memory blocks.
- **Mem0:** Entity-centric fact extraction and user preference tracking across sessions.
- **Zep:** Temporal knowledge graphs and conversation summarization.

## 2. SEED-AI Memory Architecture
SEED-AI uses a robust multi-table SQLite repository (`memory/store.py`):
- **Episodic Memory:** `tasks`, `events`, `session_messages`, `session_tasks`.
- **Categorized Knowledge & Preferences:** `memory_items` table with types:
  - `durable_knowledge`
  - `user_preference` (requires approval)
  - `project_context`
  - `temporary_context`
- **Isolation:** Project and session scoping prevent cross-tenant data leakage.
