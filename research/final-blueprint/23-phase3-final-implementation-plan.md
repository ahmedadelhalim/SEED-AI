# 23-Phase 3 Final Implementation Plan: Dynamic Skills, Tools, and MCP Engine

**Document ID:** `23-phase3-final-implementation-plan`
**Project Root:** `D:\SEED-AI`
**Date:** 2026-11-12
**Status:** DESIGN AND PLANNING ONLY — No production code or database modifications performed.

---

## Executive Summary
This document establishes the final, user-approved implementation plan for **Phase 3: Dynamic Skills, Tools, and MCP Engine** in SEED-AI. It fully incorporates the user-approved policies for **Third-Party Skill Trust (MANUAL review and cryptographic digest binding)** and **MCP Server Trust (EXPLICIT configuration and approval)**.

---

## 1. User-Approved Architectural Decisions (Incorporated)

### Decision 1 — Third-Party Skill Trust Policy: MANUAL
1. Every third-party skill requires administrative review before installation and activation.
2. Skill provenance must be inspected; cryptographic signatures and hashes must be verified whenever available.
3. A missing signature does not mean a skill is malicious, but it must be explicitly disclosed. A valid signature does not guarantee safety.
4. Review covers requested permissions, dependencies, scripts, network access, data access, and risk.
5. **Skills cannot grant themselves permissions.** `PermissionEngine` remains the sole authority.
6. Installation and activation are separate lifecycle operations.
7. Approval is auditable and bound to the exact reviewed artifact version and integrity digest (`sha256`). Any change invalidates approval.

### Decision 2 — MCP Server Trust Policy: EXPLICIT
1. SEED may discover potential MCP servers, but discovery never implies authorization.
2. Every new MCP server requires explicit configuration in `mcp_servers.json` and human approval before its first connection.
3. Discovered unapproved servers remain inactive.
4. MCP tool discovery occurs *only* after an approved connection is established and capabilities are validated.
5. Changes to server identity, command, transport, credentials, or requested permissions trigger revalidation and renewed approval.
6. MCP tools enter `ToolRegistry` and use SEED's central governance pipeline.

---

## 2. Updated Skill & MCP Lifecycle States
- **Skill States:** `Discovered`, `Parsed`, `Validated`, `ProvenanceChecked`, `ReviewRequested`, `AdminApproved`, `AdminRejected`, `Installed`, `Registered`, `Activated`, `Disabled`, `Revoked`, `Uninstalled`, `RolledBack`.
- **MCP States:** `Discovered`, `Configured`, `AwaitingApproval`, `Approved`, `Connected`, `CapabilitiesDiscovered`, `Validated`, `Registered`, `ReapprovalRequired`, `Disconnected`, `Failed`, `Disabled`, `Revoked`.

---

## 3. Approval Contracts
- **Skill Approval Contract:** Bound to `skill_id`, `version`, `artifact_digest` (sha256), `provenance_metadata`, `requested_permissions`, `dependency_lock`, `reviewer_id`, `approved_at`, and `status` (`active`, `revoked`, `expired`).
- **MCP Approval Contract:** Bound to `server_id`, `transport`, `command_or_endpoint`, `config_digest`, `auth_reference_key`, `requested_permissions`, `approved_capabilities`, `reviewer_id`, `approved_at`, and `status`.

---

## 4. Reconciled Phase 3 Implementation Milestones
- **Milestone A:** Manifest schemas and strict JSON validation.
- **Milestone B:** Skill discovery and safe frontmatter parsing (`SKILL.md`).
- **Milestone C:** Provenance inspection and artifact integrity (`sha256`) verification.
- **Milestone D:** Administrative review and single-use/version-bound approval workflow.
- **Milestone E:** Skill installation, versioning, activation, disablement, revocation, and rollback.
- **Milestone F:** Dynamic `ToolRegistry` integration through central governance (`PermissionEngine`, `ApprovalManager`).
- **Milestone G:** MCP configuration management via `mcp_servers.json` with explicit approval checks.
- **Milestone H:** MCP connection lifecycle, stdio/SSE transport, and health checks.
- **Milestone I:** MCP capability validation and governed registration into SEED.
- **Milestone J:** Comprehensive security, regression, and integration acceptance testing.

---
*Verified Implementation Evidence: Designed in strict alignment with SEED's central authority invariant. No production code was modified.*
