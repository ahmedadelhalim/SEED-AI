# SEED-AI Remaining Blockers (Phase 1.5)

**Document Purpose:** Itemization of technical blockers preventing live end-to-end model execution and Phase 2 progression.

---

## Active Blockers

1. **Ollama Service Environment Disconnect:**
   - *Description:* The running Ollama background daemon was initialized without `OLLAMA_MODELS=D:\AI\Models`, so it fails to discover `qwen3:4b` despite the model blobs existing on disk.
   - *Impact:* Prevents live local model inference and live tool-calling test execution.
   - *Remediation:* Restart Ollama with `OLLAMA_MODELS=D:\AI\Models` configured in its environment (requires explicit user approval).

2. **Absence of Dynamic Skill Manifest Loader:**
   - *Description:* Tool definitions are hardcoded in `SeedApplication.__init__`, lacking a file-backed skill discovery mechanism (`SKILL.md` parser).
   - *Impact:* Limits extensibility until Phase 2/3.
   - *Remediation:* Implement skill manifest parsing in a future iteration.
