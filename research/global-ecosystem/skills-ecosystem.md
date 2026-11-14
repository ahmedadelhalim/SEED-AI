# SEED-AI Skills & Extensibility Systems

**Document Purpose:** Investigation of skill ecosystems, dynamic loading, validation, and secure execution boundaries.

---

## 1. Industry Skill Ecosystems
- **Claude Code & VS Code Agent Skills:** Modular markdown instruction files (`SKILL.md`) paired with typed tool definitions that inject domain expertise into agent context dynamically.
- **OpenAI Codex / Function Calling:** Declarative JSON schema tool specifications paired with backend execution handlers.

## 2. SEED-AI Skill & Extensibility Architecture
To prevent prompt injection and unauthorized capabilities:
1. **Registered Tool Closed Set:** Skills cannot dynamically inject arbitrary executable code; they provide structured documentation and parameter schemas that map exclusively to pre-registered handlers in `ToolRegistry`.
2. **Granular Scoping:** Every skill/tool carries explicit action (`read`, `write`, `execute`) and scope (`workspace`, `system`, `network`) metadata evaluated by `PermissionEngine`.
3. **Audit Trail:** Every skill invocation writes structured audit events (`events` table) linked to the parent task ID.
