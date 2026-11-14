from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from core.tool_registry import ToolError, ToolRegistry


class PlanValidationError(ValueError):
    pass


@dataclass(frozen=True)
class PlannedStep:
    step_id: str
    name: str
    tool: str
    arguments: Mapping[str, Any]
    dependencies: Tuple[str, ...]
    expected_result: str
    verification: str
    risk: str


@dataclass(frozen=True)
class PlanningContract:
    objective: str
    steps: Tuple[PlannedStep, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], tools: ToolRegistry):
        if not isinstance(value, Mapping) or not isinstance(value.get("objective"), str) or not value["objective"].strip():
            raise PlanValidationError("Plan objective is required")
        raw_steps = value.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise PlanValidationError("Plan must contain at least one step")
        steps = []
        seen = set()
        for raw in raw_steps:
            if not isinstance(raw, Mapping):
                raise PlanValidationError("Each plan step must be an object")
            required = ("step_id", "name", "tool", "arguments", "dependencies", "expected_result", "verification", "risk")
            if any(key not in raw for key in required):
                raise PlanValidationError("Plan step is missing required fields")
            step_id = raw["step_id"]
            if not isinstance(step_id, str) or not step_id or step_id in seen:
                raise PlanValidationError("Plan step identifiers must be unique strings")
            seen.add(step_id)
            tool_name = raw["tool"]
            tool = tools.get(tool_name) if isinstance(tool_name, str) else None
            if tool is None:
                raise PlanValidationError(f"Plan references an unregistered tool: {tool_name}")
            arguments = raw["arguments"]
            try:
                tool.validate_arguments(arguments)
            except (ToolError, TypeError) as error:
                raise PlanValidationError(f"Invalid arguments for {tool_name}") from error
            dependencies = raw["dependencies"]
            if not isinstance(dependencies, list) or any(not isinstance(dep, str) for dep in dependencies):
                raise PlanValidationError("Step dependencies must be a list of identifiers")
            risk = raw["risk"]
            if risk not in {"read", "write", "destructive"}:
                raise PlanValidationError("Invalid step risk classification")
            steps.append(PlannedStep(
                step_id=step_id, name=raw["name"], tool=tool_name,
                arguments=arguments, dependencies=tuple(dependencies),
                expected_result=raw["expected_result"], verification=raw["verification"], risk=risk,
            ))
        ids = {step.step_id for step in steps}
        if any(dep not in ids for step in steps for dep in step.dependencies):
            raise PlanValidationError("Plan references an unknown dependency")
        _ensure_acyclic(steps)
        return cls(objective=value["objective"], steps=tuple(steps))


def _ensure_acyclic(steps):
    graph = {step.step_id: set(step.dependencies) for step in steps}
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            raise PlanValidationError("Plan dependency cycle detected")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
