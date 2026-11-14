# 16-Final Target Architecture

**Document ID:** `16-final-target-architecture`
**Date:** 2026-11-12

---

## 1. Subsystems
Unified modular monolith anchored around `SeedApplication.seed_request()` and `SeedOrchestrator`, with isolated worker subprocesses for heavy ML/audio workloads and strict central governance over all tools and skills.
