"""
Phase 9.4 Telemetry & Tool Performance Benchmark Script
Measures actual latency across text completion, minimal tools, full tools, and validates governance independently.
"""

import time
import json
import urllib.request
from brain.model_gateway import ModelGateway
from brain.model_types import ModelRequest
from core.application import SeedApplication
from core.tool_registry import ToolDefinition
from security.permission_engine import ExecutionIdentity, DecisionOutcome


def benchmark():
    print("=== 1. BASELINE LATENCY MEASUREMENTS ===")
    gateway = ModelGateway.with_local_defaults()
    
    # A. Text completion without tools
    start = time.monotonic()
    try:
        resp = gateway.complete(ModelRequest(
            messages=({"role": "user", "content": "Say hello."},),
            model="qwen3:4b",
            timeout_seconds=60,
        ))
        duration = time.monotonic() - start
        print(f"[PASS] Text completion without tools: {duration:.2f}s | Response: {resp.content!r}")
    except Exception as e:
        duration = time.monotonic() - start
        print(f"[FAIL] Text completion without tools: {duration:.2f}s | Error: {e}")

    # B. Completion with minimal tool
    min_tools = ({
        "type": "function",
        "function": {
            "name": "system.health",
            "description": "Get system health metrics.",
            "parameters": {"type": "object", "properties": {}},
        },
    },)
    start = time.monotonic()
    try:
        resp = gateway.complete(ModelRequest(
            messages=({"role": "user", "content": "Call system.health tool."},),
            model="qwen3:4b",
            tools=min_tools,
            timeout_seconds=120,
        ))
        duration = time.monotonic() - start
        print(f"[PASS] Completion with minimal tool: {duration:.2f}s | Content: {resp.content!r} | Tool Calls: {resp.tool_calls}")
    except Exception as e:
        duration = time.monotonic() - start
        print(f"[FAIL] Completion with minimal tool: {duration:.2f}s | Error: {e}")

    # C. Completion with full registered tool set from SeedApplication
    app = SeedApplication()
    all_tools = app.tools.model_tools()
    start = time.monotonic()
    try:
        resp = gateway.complete(ModelRequest(
            messages=({"role": "user", "content": "Call system.health tool now."},),
            model="qwen3:4b",
            tools=all_tools,
            timeout_seconds=180,
        ))
        duration = time.monotonic() - start
        print(f"[PASS] Completion with full tool set ({len(all_tools)} tools): {duration:.2f}s | Content: {resp.content!r} | Tool Calls: {resp.tool_calls}")
    except Exception as e:
        duration = time.monotonic() - start
        print(f"[FAIL] Completion with full tool set: {duration:.2f}s | Error: {e}")

    print("\n=== 2. INDEPENDENT GOVERNANCE TESTS ==0")
    # Test governance with synthetic tool calls
    identity = ExecutionIdentity(principal_id="test-user")
    
    # Authorized tool
    decision_health = app.permissions.check("read", "system.health", "system", identity=identity)
    print("Governance check 'system.health':", decision_health.outcome.value, "| Allowed:", decision_health.allowed)
    
    # Unknown/Unregistered tool
    decision_unknown = app.permissions.check("execute", "system.unknown", "system", identity=identity)
    print("Governance check 'system.unknown':", decision_unknown.outcome.value, "| Allowed:", decision_unknown.allowed, "| Reason:", decision_unknown.reason)

    # Approval-required tool (file.write)
    decision_write = app.permissions.check("write", "file.write", "workspace", identity=identity)
    print("Governance check 'file.write':", decision_write.outcome.value, "| Requires Approval:", decision_write.requires_approval)


if __name__ == "__main__":
    benchmark()
