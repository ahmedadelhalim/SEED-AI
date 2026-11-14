from typing import Optional

from brain.model_gateway import ModelGateway
from core.operations import OperationsAPI
from core.orchestrator import SeedOrchestrator
from core.plan_engine import PlanEngine
from core.service_registry import ServiceRegistry
from core.task_engine import TaskEngine
from core.tool_registry import ToolDefinition, ToolRegistry
from interfaces.tool_adapter import MCPToolAdapter
from runtime.agent_runtime import AgentRuntime
from runtime.file_tools import FileTools
from runtime.windows.tools import WindowsDiscoveryTools
from runtime.skills.registry import GovernedDynamicToolRegistry
from security.permission_engine import PermissionEngine


class SeedApplication:
    """Shared composition root for SEED clients and transports."""

    def __init__(self, gateway: Optional[ModelGateway] = None,
                 tasks: Optional[TaskEngine] = None,
                 permissions: Optional[PermissionEngine] = None):
        self.tasks = tasks or TaskEngine()
        self.permissions = permissions or PermissionEngine()
        self.plan_engine = PlanEngine()
        self.agent = AgentRuntime(self.tasks, self.permissions)
        self.file_tools = FileTools()
        self.tools = ToolRegistry()
        self.tools.register(ToolDefinition(
            name="workspace.list",
            description="List files and directories inside the authorized SEED workspace.",
            handler=self.agent.list_workspace_entries,
            parameters={
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": [],
                "additionalProperties": False,
            },
            action="read",
            scope="workspace",
            parallel_safe=True,
        ))
        self.gateway = gateway or ModelGateway.with_local_defaults()
        self.services = ServiceRegistry()
        self.operations = OperationsAPI(
            self.gateway, self.tools, self.services
        )
        self.tools.register(ToolDefinition(
            name="system.health",
            description="Read local system memory, processor, disk, and SEED process metrics.",
            handler=self.operations.resource_snapshot,
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            action="read",
            scope="system",
            parallel_safe=True,
        ))
        self.tools.register(ToolDefinition(
            name="file.read",
            description="Read text contents of a file inside the authorized workspace with optional line bounds.",
            handler=self.file_tools.read,
            parameters={
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                    "max_bytes": {"type": "integer"},
                },
                "required": ["relative_path"],
                "additionalProperties": False,
            },
            action="read",
            scope="workspace",
            parallel_safe=True,
            retry_safe=True,
        ))
        self.tools.register(ToolDefinition(
            name="file.search",
            description="Search filenames and file contents within the authorized workspace.",
            handler=self.file_tools.search,
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "relative_path": {"type": "string"},
                    "file_pattern": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
            action="read",
            scope="workspace",
            parallel_safe=True,
            retry_safe=True,
        ))
        self.tools.register(ToolDefinition(
            name="file.write",
            description="Create or write text to a file inside the authorized workspace. Requires explicit approval.",
            handler=self.file_tools.write,
            parameters={
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string"},
                    "content": {"type": "string"},
                    "allow_overwrite": {"type": "boolean"},
                },
                "required": ["relative_path", "content"],
                "additionalProperties": False,
            },
            action="write",
            scope="workspace",
            parallel_safe=False,
            retry_safe=False,
        ))
        self.services.register("workspace.list", "tool")
        self.services.register("system.health", "tool")
        self.services.register("file.read", "tool")
        self.services.register("file.search", "tool")
        self.services.register("file.write", "tool")
        self.services.register("system.windows_host", "tool")
        self.services.register("system.windows_cpu_memory", "tool")
        self.services.register("system.windows_disk_volumes", "tool")
        self.services.register("system.windows_processes", "tool")
        self.services.register("system.windows_network", "tool")
        self.tools.register(ToolDefinition(
            name="system.windows_host",
            description="Collect Windows host information.",
            handler=WindowsDiscoveryTools.host_info,
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            action="read",
            scope="system",
            parallel_safe=True,
            retry_safe=True,
        ))
        self.tools.register(ToolDefinition(
            name="system.windows_cpu_memory",
            description="Collect Windows CPU and memory metrics.",
            handler=WindowsDiscoveryTools.cpu_memory,
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            action="read",
            scope="system",
            parallel_safe=True,
            retry_safe=True,
        ))
        self.tools.register(ToolDefinition(
            name="system.windows_disk_volumes",
            description="Collect Windows disk partitions and volume usage.",
            handler=WindowsDiscoveryTools.disk_volumes,
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            action="read",
            scope="system",
            parallel_safe=True,
            retry_safe=True,
        ))
        self.tools.register(ToolDefinition(
            name="system.windows_processes",
            description="List running Windows processes sample.",
            handler=WindowsDiscoveryTools.running_processes,
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                },
                "required": [],
                "additionalProperties": False,
            },
            action="read",
            scope="system",
            parallel_safe=True,
            retry_safe=True,
        ))
        self.tools.register(ToolDefinition(
            name="system.windows_network",
            description="Collect Windows network interfaces and connections.",
            handler=WindowsDiscoveryTools.network_info,
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            action="read",
            scope="system",
            parallel_safe=True,
            retry_safe=True,
        ))
        self.services.register("mcp-stdio", "transport")

        # Automatically recover approved dynamic tools from SQLite storage during initialization
        GovernedDynamicToolRegistry.recover_approved_tools_on_startup(self.tools, self.permissions)

        self.orchestrator = SeedOrchestrator(
            gateway=self.gateway,
            tools=self.tools,
            permissions=self.permissions,
            tasks=self.tasks,
        )
        self.tool_adapter = MCPToolAdapter(
            self.tools, self.permissions, self.tasks
        )

    def seed_request(self, user_request, session_id=None, approval_id=None):
        return self.orchestrator.run(
            user_request,
            session_id=session_id,
            approval_id=approval_id,
        )