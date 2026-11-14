# 08-Memory and Knowledge Comparison

**Document ID:** `08-memory-knowledge-comparison`
**Date:** 2026-11-12

---

## 1. Hybrid Memory Strategy
- **Relational Storage:** SQLite (`memory/store.py`) for operational tasks, events, sessions, and categorized memory items.
- **Semantic Storage:** Embedded Qdrant vector store (`data/qdrant`) for hybrid retrieval and document chunking.
