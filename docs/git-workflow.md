# SEED-AI Git Automation & Synchronization Workflow

## Overview
The `scripts\git-sync.ps1` PowerShell script provides a robust, safe, and automated Git workflow for the SEED-AI project at `D:\SEED-AI`. It integrates with Git Credential Manager (GCM), enforces strict safety checks against sensitive and temporary files, performs selective staging, generates Conventional Commits, and verifies remote synchronization.

---

## Supported Modes

1. **Status** (`-Mode Status`):
   - Inspects the repository state and current feature branch.
2. **Check** (`-Mode Check`):
   - Runs full repository validation, scans for sensitive files (`.env`, `.db`, `__pycache__`, `.venv`, etc.), and checks for whitespace errors using `git diff --check`.
3. **Commit** (`-Mode Commit`):
   - Executes safety checks, selectively stages approved source and documentation paths (`brain/`, `tests/`, `docs/`, `*.md`, `*.toml`, `*.ps1`), and creates a Conventional Commit.
4. **Push** (`-Mode Push`):
   - Fetches from `origin`, verifies branch tracking, and pushes to the current branch via Git Credential Manager.
5. **Sync** (`-Mode Sync` [Default]):
   - Executes the complete end-to-end safe workflow: Check → Commit → Push.

---

## Safety Guarantees
- **No Unsafe Staging:** Never blindly stages all files (`git add -A`). Only approved directories and file types are staged.
- **Sensitive File Block:** Automatically aborts if `.env`, SQLite databases (`.db`), caches, or credentials are detected.
- **No Force Pushes:** Strictly prohibits destructive force pushes.
- **GCM Integration:** Relies on Windows Credential Manager without exposing or storing tokens in project files.
