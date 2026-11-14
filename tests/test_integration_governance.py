import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.tool_registry import ToolRegistry
from integrations.http import HttpIntegration, register_http_integration
from memory import store
from security.permission_engine import PermissionEngine


class IntegrationGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch = patch.object(store, "DB_PATH", Path(self.tmp.name) / "integration.sqlite")
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_read_http_integration_is_registered_and_permission_checked(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"healthy": true}'

        integration = HttpIntegration("http://127.0.0.1:1", opener=lambda request, timeout: Response())
        tools = ToolRegistry()
        permissions = PermissionEngine()
        name = register_http_integration("local", integration, tools, permissions)
        tool = tools.get(name)
        self.assertIsNotNone(tool)
        self.assertEqual(tool.action, "read")
        self.assertEqual(tool.scope, "network")
        self.assertEqual(tool.handler(method="GET", path="/health", body=None)["body"], {"healthy": True})
        self.assertTrue(permissions.check("read", name, "network").allowed)

    def test_http_integration_rejects_non_get_in_read_only_registration(self):
        integration = HttpIntegration("http://example.test", opener=lambda request, timeout: None)
        tools = ToolRegistry()
        permissions = PermissionEngine()
        name = register_http_integration("example", integration, tools, permissions)
        with self.assertRaises(ValueError):
            tools.get(name).handler(method="POST", path="/write", body={"x": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
