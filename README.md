# SEED-AI: Secure Autonomous AI Agent & Orchestration Engine

SEED-AI is an advanced, secure autonomous AI agent orchestration and runtime environment designed for local execution, governed tool execution, robust memory persistence, and multi-model inference.

## 🎯 Current Milestone & Governance Status

- **Branch:** `clean/seed-phase1-remediation`
- **Phase 1 Implementation:** COMPLETED & ACCEPTED
- **RR-01 Final Acceptance:** **PASS**
- **RR-02 Status:** Design and review closure only. RR-02 implementation is **NOT AUTHORIZED** per governance constraints. No production deployment is authorized.

---

## 🏗️ Project Architecture & Components

- **Core Engine (`/core/`):** Autonomous agent loop, resource governance, cryptographic audit logging, and orchestrators.
- **Brain (`/brain/`):** Model gateway supporting local inference providers (including `llama_cpp_python` with Qwen3 4B GGUF) and fallback capabilities.
- **Memory (`/memory/`):** SQLite-backed persistent memory store with hybrid semantic recall and structured governance.
- **Desktop UI (`/desktop/`):** Interactive desktop companion interface for chat and agent workflow visualization.
- **Tests (`/tests/`):** Comprehensive test suites validating unit logic, agent loops, isolation, memory persistence, and real inference.

---

## ⚙️ Environment & Installation

1. **Python Environment:** Python 3.14 (or compatible Python 3.10+) with virtual environment (`.venv`).
2. **Dependencies:** Managed via `pyproject.toml`. Install packages using:
   ```powershell
   pip install -e .
   ```
3. **Local Model Setup:** GGUF models (such as Qwen3 4B) placed in local model directories (e.g., `D:\AI\Models`).

---

## 🚀 Running and Testing

- **Run Interactive Chat / Desktop:**
  ```powershell
  python run_interactive_chat.py
  ```
- **Execute Test Suite:**
  ```powershell
  python -m pytest
  ```

---

## 🔒 Recovery & Restoration Instructions

In the event of system failure or migration to a new Windows workstation:
1. Clone the repository and checkout `clean/seed-phase1-remediation`.
2. Restore or initialize local Python virtual environment (`.venv`) and install dependencies from `pyproject.toml`.
3. Restore local SQLite memory/runtime databases from the preserved recovery archive (`D:\SEED-AI-recovery\`).
4. Ensure local model paths match expected configuration.

---

## 📜 Governance & Compliance
- **Default-Deny Security:** Strict workspace guarding and explicit write approvals.
- **Audit Trails:** Cryptographic audit logs ensure full provenance tracking across agent actions.
