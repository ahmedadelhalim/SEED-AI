import json
import os
import time
from typing import Any, Mapping

from brain.model_types import ModelRequest
from core.planning import PlanValidationError, PlanningContract


PLANNING_SYSTEM_PROMPT = """You are SEED's planning component. Return ONLY valid JSON.
Create a safe executable plan for the user's objective using only the registered tools below.
Never invent tools, permissions, approvals, credentials, or execution results.
Use exact tool argument schemas. Dependencies reference step_id values.
Each step must include: step_id, name, tool, arguments, dependencies, expected_result, verification, risk.
Risk must be read, write, or destructive. Do not perform execution; only propose the plan.
"""


class LivePlanningError(RuntimeError):
    pass


class LivePlanner:
    def __init__(self, gateway, tools, max_attempts=2):
        self.gateway = gateway
        self.tools = tools
        self.max_attempts = max_attempts

    def prompt(self, objective: str) -> str:
        tools = json.dumps(list(self.tools.model_tools()), ensure_ascii=True, separators=(",", ":"))
        return PLANNING_SYSTEM_PROMPT + "\nRegistered tools:\n" + tools + "\nUser objective:\n" + objective

    def generate(self, objective: str, model: str = None, provider: str = None):
        if not objective or not objective.strip():
            raise ValueError("Planning objective is required")
        last_error = None
        started = time.perf_counter()
        timeout_seconds = float(os.environ.get("SEED_PLANNING_TIMEOUT_SECONDS", "300"))
        # Keep planning prompts compact enough for local CPU inference while
        # retaining the complete schema contract and registered tool names.
        compact_tools = []
        for tool in self.tools.model_tools():
            function = tool.get("function", {})
            compact_tools.append({
                "name": function.get("name"),
                "description": function.get("description"),
                "parameters": function.get("parameters"),
            })
        messages = ({"role": "system", "content": PLANNING_SYSTEM_PROMPT}, {"role": "user", "content": PLANNING_SYSTEM_PROMPT + "\nRegistered tool contracts:\n" + json.dumps(compact_tools, ensure_ascii=True, separators=(",", ":")) + "\nObjective:\n" + objective})
        for attempt in range(self.max_attempts):
            request = ModelRequest(
                messages=messages, model=model, provider=provider,
                timeout_seconds=timeout_seconds,
                response_format={"type": "json"},
            )
            try:
                response = self.gateway.complete(request, provider_name=provider)
                payload = json.loads(response.content)
                contract = PlanningContract.from_mapping(payload, self.tools)
                return {"contract": contract, "attempts": attempt + 1, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
            except (json.JSONDecodeError, PlanValidationError, ValueError) as error:
                last_error = error
                messages = messages + ({"role": "user", "content": "The proposed JSON plan was invalid. Return corrected JSON only; do not execute anything. Error: " + str(error)},)
        raise LivePlanningError("Qwen did not produce a valid executable plan") from last_error
