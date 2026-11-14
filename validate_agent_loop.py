"""
Phase 9.5 — Full Agent Execution Loop Validation Script
Executes and captures evidence for complete tool cycles, denied executions, and approval workflows through SeedApplication.
"""

import time
import json
from core.application import SeedApplication
from memory import store


def validate_loop():
    print("=== SCENARIO 1: COMPLETE HARMLESS TOOL CYCLE (system.health) ===")
    app = SeedApplication()
    start = time.monotonic()
    
    # We can invoke seed_request with a request asking for system health
    try:
        result = app.seed_request(
            "Call the system.health tool now with no arguments. Reply with HEALTH_OK when finished.",
            session_id="loop-health"
        )
        duration = time.monotonic() - start
        print(f"Status: {result.status}")
        print(f"Response: {result.response}")
        print(f"Tool Results: {result.tool_results}")
        print(f"Duration: {duration:.2f}s")
    except Exception as e:
        print(f"Scenario 1 Exception: {e}")

    print("\n=== SCENARIO 2: DENIED UNREGISTERED TOOL EXECUTION ===")
    start = time.monotonic()
    try:
        result = app.seed_request(
            "Call the tool named system.command with argument command set to whoami.",
            session_id="loop-deny"
        )
        duration = time.monotonic() - start
        print(f"Status: {result.status}")
        print(f"Response: {result.response}")
        print(f"Tool Results: {result.tool_results}")
        print(f"Duration: {duration:.2f}s")
    except Exception as e:
        print(f"Scenario 2 Exception: {e}")

    print("\n=== SCENARIO 3: APPROVAL-REQUIRED WORKFLOW (file.write) ===")
    start = time.monotonic()
    try:
        result = app.seed_request(
            "Write 'hello seed' to test_output.txt using file.write tool.",
            session_id="loop-approval"
        )
        duration = time.monotonic() - start
        print(f"Status: {result.status}")
        print(f"Response: {result.response}")
        print(f"Pending Approvals: {result.pending_approvals}")
        print(f"Duration: {duration:.2f}s")
    except Exception as e:
        print(f"Scenario 3 Exception: {e}")


if __name__ == "__main__":
    validate_loop()
