# 07-Memory and Knowledge Specification

**Document ID:** `07-memory-knowledge-specification`
**Date:** 2026-11-12

---

## 1. Unified Memory Hierarchy
- **Relational Storage:** SQLite (`memory/store.py`) for tasks, events, sessions, dialogue history, and structured memory items.
- **Semantic Vector Storage:** Embedded Qdrant vector store (`D:/SEED-AI/data/qdrant`) for hybrid semantic retrieval and document chunking.
- **Privacy & Retention:** Project and session isolation; expiration dates (`expires_at`) for temporary context; user preference modification restricted by approval requirements.
