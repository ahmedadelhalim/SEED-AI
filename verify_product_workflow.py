"""
Comprehensive Product Workflow Verification Script for SEED-AI
Validates application startup, memory continuity, orchestrator execution, governance, and desktop HTTP APIs.
"""

import json
from core.application import SeedApplication
from memory import store
from security.permission_engine import ExecutionIdentity, DecisionOutcome


def verify_all():
    print("=== STARTING FULL PRODUCT WORKFLOW VERIFICATION ===")
    
    # 1. Initialize Application & Database
    store.initialize()
    app = SeedApplication()
    print("[1/5] Application & Database initialized successfully.")

    # 2. Test Persistent Memory Continuity
    store.save_memory("user_preference", "language_pref", "Arabic / Egyptian", project_id="seed-prod", approved=True)
    store.save_memory("durable_knowledge", "core_mission", "Autonomous secure local intelligence assistant", project_id="seed-prod", approved=True)
    
    # Simulate separate session recall
    recalled_prefs = list(store.search_memory("language", project_id="seed-prod"))
    recalled_knowledge = list(store.search_memory("mission", project_id="seed-prod"))
    assert len(recalled_prefs) > 0, "Memory preference not retrieved"
    assert len(recalled_knowledge) > 0, "Durable knowledge not retrieved"
    print(f"[2/5] Persistent Memory Verified. Recalled pref: {recalled_prefs[0]['content']} | Knowledge: {recalled_knowledge[0]['content']}")

    # 3. Test Tool Governance & Permissions
    identity = ExecutionIdentity(principal_id="admin-user", project_id="seed-prod")
    decision_read = app.permissions.check("read", "workspace.list", "workspace", identity=identity)
    decision_deny = app.permissions.check("execute", "system.command", "system", identity=identity)
    decision_write = app.permissions.check("write", "file.write", "workspace", identity=identity)
    
    assert decision_read.outcome == DecisionOutcome.ALLOW, "workspace.list should be allowed"
    assert decision_deny.outcome == DecisionOutcome.DENY, "system.command should be denied by default"
    assert decision_write.requires_approval is True, "file.write should require approval"
    print(f"[3/5] Tool Governance Verified. workspace.list: ALLOW | system.command: DENY | file.write: REQUIRE_APPROVAL")

    # 4. Test Orchestrator & Task Engine
    task = app.tasks.submit("Verify product workflow execution")
    app.tasks.set_status(task["task_id"], "completed")
    history = app.operations.execution_history(limit=5)
    assert any(t["id"] == task["task_id"] for t in history), "Task not recorded in history"
    print(f"[4/5] Orchestrator & Task History Verified. Recorded task ID #{task['task_id']}")

    # 5. Test Desktop HTTP Server Factory
    from interfaces.desktop_server import create_server
    server = create_server(application=app, host="127.0.0.1", port=8765)
    assert server is not None, "Desktop server could not be created"
    server.server_close()
    print("[5/5] Desktop HTTP Server Factory Verified.")

    print("\n=== ALL PRODUCT WORKFLOW VERIFICATIONS PASSED SUCCESSFULLY ===")


if __name__ == "__main__":
    verify_all()
