from unittest import TestCase
from runtime.windows.discovery import WindowsDiscovery
from runtime.windows.tools import WindowsDiscoveryTools
from security.permission_engine import PermissionEngine
from core.tool_registry import ToolDefinition, ToolRegistry


class Phase2ADiscoveryTests(TestCase):
    def test_windows_discovery_collects_host_metrics(self):
        info = WindowsDiscovery.host_info()
        self.assertIn("system", info)
        self.assertIn("machine", info)

        cpu_mem = WindowsDiscovery.cpu_memory()
        self.assertIn("physical_cores", cpu_mem)
        self.assertIn("memory", cpu_mem)

        disk = WindowsDiscovery.disk_volumes()
        self.assertEqual(disk["status"], "success")
        self.assertIsInstance(disk["partitions"], list)

        procs = WindowsDiscovery.running_processes(limit=10)
        self.assertEqual(procs["status"], "success")
        self.assertIsInstance(procs["processes"], list)

        net = WindowsDiscovery.network_info()
        self.assertEqual(net["status"], "success")
        self.assertIn("interfaces", net)

    def test_phase2a_tools_registered_and_governed(self):
        registry = ToolRegistry()
        engine = PermissionEngine()

        registry.register(ToolDefinition(
            name="system.windows_host",
            description="Collect Windows host information.",
            handler=WindowsDiscoveryTools.host_info,
            parameters={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            action="read",
            scope="system",
            parallel_safe=True,
        ))

        decision = engine.check("read", "system.windows_host", "system")
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.requires_approval)

        tool = registry.get("system.windows_host")
        result = tool.handler()
        self.assertEqual(result["status"], "success")
        self.assertIn("system", result["data"])
