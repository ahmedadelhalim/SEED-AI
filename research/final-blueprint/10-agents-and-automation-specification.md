# 10-Agents and Automation Specification

**Document ID:** `10-agents-and-automation-specification`
**Date:** 2026-11-12

---

## 1. Subagent Delegation
- Subagents operate strictly under `SeedOrchestrator` supervision.
- Assigned specific scopes, input/output contracts, and allowed tool subsets.
- All actions pass through central permission and approval layers.
- Background Automation: Scheduled tasks and cron-like triggers operating with least-privilege identity bounds.
