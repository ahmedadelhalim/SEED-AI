# 05-Skills, Tools, and MCP Specification

**Document ID:** `05-skills-tools-mcp-specification`
**Date:** 2026-11-12

---

## 1. Skill Manifest Format (`SKILL.md`)
Skills combine markdown instructions with a YAML frontmatter manifest:
```yaml
---
name: file-management
version: "1.0.0"
description: Governed filesystem operations
permissions:
  - action: read
    scope: workspace
  - action: write
    scope: workspace
tools:
  - file.read
  - file.search
  - file.write
---
```
- **Central Authority Rule:** Skills cannot grant themselves permissions; `PermissionEngine` independently evaluates all requests against registered security policies.
