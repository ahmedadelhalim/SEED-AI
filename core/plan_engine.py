from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple
import json
import uuid

from memory import store


PLAN_STATES = {"pending", "running", "completed", "failed", "blocked", "cancelled"}
STEP_STATES = PLAN_STATES


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    plan_id: str
    name: str
    dependencies: Tuple[str, ...] = ()
    state: str = "pending"
    result: Optional[Mapping[str, Any]] = None
    evidence: Tuple[Mapping[str, Any], ...] = ()


class PlanEngine:
    """Durable plan state owned by SEED; execution remains in SeedOrchestrator."""

    def create_plan(self, objective: str, steps: Iterable[Mapping[str, Any]], plan_id: Optional[str] = None) -> str:
        store.initialize()
        if not objective or not isinstance(objective, str):
            raise ValueError("Plan objective is required")
        plan_id = plan_id or uuid.uuid4().hex
        normalized = []
        for index, item in enumerate(steps, 1):
            step_id = str(item.get("step_id") or f"step-{index}")
            dependencies = tuple(str(value) for value in item.get("dependencies", ()))
            normalized.append({"step_id": step_id, "name": str(item.get("name") or step_id), "dependencies": dependencies})
        if not normalized:
            raise ValueError("A plan requires at least one step")
        store.create_plan(plan_id, objective, normalized)
        return plan_id

    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        return store.get_plan(plan_id)

    def next_steps(self, plan_id: str) -> Tuple[PlanStep, ...]:
        plan = store.get_plan(plan_id)
        if plan is None:
            raise KeyError(plan_id)
        completed = {step["step_id"] for step in plan["steps"] if step["state"] == "completed"}
        ready = []
        for step in plan["steps"]:
            if step["state"] != "pending":
                continue
            if all(dep in completed for dep in step["dependencies"]):
                ready.append(PlanStep(
                    step_id=step["step_id"], plan_id=plan_id, name=step["name"],
                    dependencies=tuple(step["dependencies"]), state=step["state"],
                    result=step["result"], evidence=tuple(step["evidence"]),
                ))
        return tuple(ready)

    def claim_step(self, plan_id: str, step_id: str) -> bool:
        plan = store.get_plan(plan_id)
        if plan is None:
            raise KeyError(plan_id)
        step = next((item for item in plan["steps"] if item["step_id"] == step_id), None)
        if step is None:
            raise KeyError(step_id)
        if step["state"] != "pending":
            return False
        if not all(dep_state == "completed" for dep_state in (
            next(item["state"] for item in plan["steps"] if item["step_id"] == dep)
            for dep in step["dependencies"]
        )):
            return False
        return store.update_plan_step(plan_id, step_id, "running")

    def complete_step(self, plan_id: str, step_id: str, result: Mapping[str, Any], evidence: Iterable[Mapping[str, Any]] = ()) -> bool:
        return store.update_plan_step(plan_id, step_id, "completed", result, tuple(evidence))

    def fail_step(self, plan_id: str, step_id: str, result: Mapping[str, Any], evidence: Iterable[Mapping[str, Any]] = ()) -> bool:
        changed = store.update_plan_step(plan_id, step_id, "failed", result, tuple(evidence))
        if changed:
            store.block_dependent_plan_steps(plan_id, step_id)
        return changed

    def resume(self, plan_id: str) -> Dict[str, Any]:
        plan = store.get_plan(plan_id)
        if plan is None:
            raise KeyError(plan_id)
        for step in plan["steps"]:
            if step["state"] == "running":
                store.update_plan_step(plan_id, step["step_id"], "pending", {"recovered": True}, ({"event": "startup_recovery"},))
        store.refresh_plan_state(plan_id)
        return store.get_plan(plan_id)

    def create_from_contract(self, contract):
        return self.create_plan(
            contract.objective,
            [{
                "step_id": step.step_id,
                "name": step.name,
                "dependencies": step.dependencies,
                "tool": step.tool,
                "arguments": dict(step.arguments),
                "expected_result": step.expected_result,
                "verification": step.verification,
                "risk": step.risk,
            } for step in contract.steps],
        )

    def status(self, plan_id: str):
        return self.get_plan(plan_id)

    def cancel(self, plan_id: str):
        return store.cancel_plan(plan_id)
