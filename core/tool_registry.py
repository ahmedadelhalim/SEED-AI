from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple


class ToolError(ValueError):
    pass


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    handler: Callable[..., Any]
    parameters: Mapping[str, Any]
    action: str
    scope: str
    parallel_safe: bool = False
    retry_safe: bool = False
    max_attempts: int = 1

    def __post_init__(self):
        if not self.name or not self.action or not self.scope:
            raise ValueError("Tool name, action, and scope are required")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if self.parallel_safe and self.action != "read":
            raise ValueError("Only read actions can be marked parallel safe")

    def validate_arguments(self, arguments: Mapping[str, Any]):
        if not isinstance(arguments, Mapping):
            raise ToolError("Tool arguments must be an object")

        properties = self.parameters.get("properties", {})
        required = self.parameters.get("required", ())
        if not isinstance(properties, Mapping) or not isinstance(required, (list, tuple)):
            raise ToolError("Tool schema is invalid")
        if any(name not in arguments for name in required):
            raise ToolError("Required tool arguments are missing")
        if self.parameters.get("additionalProperties", False) is False:
            if any(name not in properties for name in arguments):
                raise ToolError("Unexpected tool arguments are not allowed")

        for name, value in arguments.items():
            specification = properties.get(name)
            if not isinstance(specification, Mapping):
                continue
            expected = specification.get("type")
            valid = {
                "string": lambda item: isinstance(item, str),
                "boolean": lambda item: isinstance(item, bool),
                "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
                "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
                "object": lambda item: isinstance(item, Mapping),
                "array": lambda item: isinstance(item, (list, tuple)),
                "null": lambda item: item is None,
            }.get(expected)
            if valid is not None and not valid(value):
                raise ToolError("Tool argument has an invalid type")


class ToolRegistry:
    STATIC_TOOL_NAMES = {
        "workspace.list", "system.health", "file.read", "file.search", "file.write",
        "system.windows_host", "system.windows_cpu_memory", "system.windows_disk_volumes",
        "system.windows_processes", "system.windows_network",
    }

    def __init__(self):
        self._tools = {}  # type: Dict[str, ToolDefinition]

    def register(self, tool: ToolDefinition):
        if tool.name in self._tools:
            raise ValueError("Tool is already registered")
        if tool.parameters.get("type") != "object":
            raise ValueError("Tool parameters must use an object schema")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def __contains__(self, name: str):
        return name in self._tools

    def __len__(self):
        return len(self._tools)

    def list_tools(self) -> Tuple[ToolDefinition, ...]:
        """Return all registered tools"""
        return tuple(self._tools.values())

    def model_tools(self) -> Tuple[Mapping[str, Any], ...]:
        return tuple({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": dict(tool.parameters),
            },
        } for tool in self._tools.values())

    def unregister_with_ownership(self, name: str, skill_id: str, artifact_digest: str) -> bool:
        tool = self._tools.get(name)
        if not tool:
            return False
        handler = getattr(tool, "handler", None)
        # Avoid importing the registry implementation here: ownership is proven
        # by the immutable handler bindings, not by a concrete handler class.
        if (
            handler is None
            or getattr(handler, "skill_id", None) != skill_id
            or getattr(handler, "artifact_digest", None) != artifact_digest
            or not callable(handler)
        ):
            return False
        del self._tools[name]
        return True