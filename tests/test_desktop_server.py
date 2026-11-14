import json
import re
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from brain.model_types import ModelResponse, ToolCall
from core.application import SeedApplication
from interfaces.desktop_server import create_server
from memory import store
from runtime import workspace_guard
from security.permission_engine import PermissionEngine


class FakeGateway:
    default_provider = "test"
    provider_names = ("test",)

    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, _request, provider_name=None):
        return self.responses.pop(0)

    def health(self):
        return {}


class DesktopServerTests(TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        root = Path(temporary_directory.name)
        self.database_path = root / "desktop.sqlite"
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "fixture.txt").write_text("temporary only", encoding="utf-8")

        database_patcher = patch.object(store, "DB_PATH", self.database_path)
        workspace_patcher = patch.object(workspace_guard, "WORKSPACE", self.workspace)
        database_patcher.start()
        workspace_patcher.start()
        self.addCleanup(workspace_patcher.stop)
        self.addCleanup(database_patcher.stop)

        gateway = FakeGateway((
            ModelResponse(
                "",
                "test",
                "test-model",
                (ToolCall("desktop-call", "workspace.list", {"relative_path": "."}),),
            ),
            ModelResponse("SEED desktop acceptance complete.", "test", "test-model"),
        ))
        self.application = SeedApplication(gateway=gateway)
        self.assertIn("mcp-stdio", self.application.services)
        self.server = create_server(self.application, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base_url = "http://127.0.0.1:" + str(self.server.server_port)
        self.csrf = self.server.csrf_token

    def get_json(self, path):
        with urllib.request.urlopen(self.base_url + path, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def post_json(self, path, payload, csrf=True, origin=None):
        headers = {"Content-Type": "application/json"}
        if csrf:
            headers["X-SEED-CSRF"] = self.csrf
        headers["Origin"] = origin or self.base_url
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        return urllib.request.urlopen(request, timeout=10)

    def test_dashboard_uses_seed_request_and_persists_authorized_tool_execution(self):
        with urllib.request.urlopen(self.base_url + "/", timeout=5) as response:
            page = response.read().decode("utf-8")
        self.assertIn(self.csrf, page)
        self.assertIn("Microphone capture is disabled", page)

        with self.post_json("/api/request", {
            "request": "List authorized workspace entries",
            "session_id": "desktop-session",
        }) as response:
            result = json.loads(response.read().decode("utf-8"))

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["response"], "SEED desktop acceptance complete.")
        self.assertEqual(result["tool_results"][0]["status"], "success")
        self.assertEqual(
            result["tool_results"][0]["result"]["entries"][0]["name"],
            "fixture.txt",
        )
        with store.connect() as database:
            event_types = [row[0] for row in database.execute(
                "SELECT event_type FROM events ORDER BY id"
            )]
        self.assertIn("permission_decision", event_types)
        self.assertIn("tool_completed", event_types)
        service_status = self.application.operations.status()["services"]
        self.assertEqual(service_status["mcp-stdio"]["status"], "registered")
        self.assertTrue(self.database_path.is_file())

    def test_system_health_runs_through_seed_registry_and_permission_path(self):
        self.application.orchestrator.gateway.responses = [
            ModelResponse(
                "",
                "test",
                "test-model",
                (ToolCall("health-call", "system.health", {}),),
            ),
            ModelResponse("System health was read successfully.", "test", "test-model"),
        ]

        with self.post_json("/api/request", {
            "request": "Inspect local system health",
            "session_id": "system-health-session",
        }) as response:
            result = json.loads(response.read().decode("utf-8"))

        self.assertEqual(result["status"], "completed")
        health = result["tool_results"][0]["result"]
        self.assertGreater(health["memory_total_bytes"], 0)
        self.assertGreater(health["logical_processor_count"], 0)
        self.assertGreaterEqual(health["disk_free_bytes"], 0)
        with store.connect() as database:
            event_types = [row[0] for row in database.execute(
                "SELECT event_type FROM events ORDER BY id"
            )]
        self.assertIn("permission_decision", event_types)
        self.assertIn("tool_completed", event_types)

    def test_post_requires_same_origin_and_csrf_token(self):
        try:
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.post_json(
                    "/api/request",
                    {"request": "must not run"},
                    csrf=False,
                )
        except OSError as error:
            self.fail(
                "CSRF request connection aborted; handler error type: "
                + str(self.server.last_handler_error)
                + " ("
                + type(error).__name__
                + ")"
            )
        self.assertEqual(raised.exception.code, 403)
        raised.exception.close()
        self.assertEqual(store.list_tasks(limit=10), [])

    def test_desktop_approval_resumes_only_through_seed_permission_path(self):
        tool_call = ToolCall(
            "approval-call",
            "workspace.list",
            {"relative_path": "."},
        )
        self.application.orchestrator.gateway.responses = [
            ModelResponse("", "test", "test-model", (tool_call,)),
            ModelResponse("", "test", "test-model", (tool_call,)),
            ModelResponse("Approved workspace listing complete.", "test", "test-model"),
        ]
        policy = {
            "action": "read",
            "scope": "workspace",
            "allowed": True,
            "approval": True,
        }

        with patch.dict(
            PermissionEngine.TOOL_POLICIES,
            {"workspace.list": policy},
        ):
            with self.post_json("/api/request", {
                "request": "List authorized workspace entries",
                "session_id": "approval-session",
            }) as response:
                pending = json.loads(response.read().decode("utf-8"))
            approval_id = pending["pending_approvals"][0]["approval_id"]
            with self.post_json("/api/approvals/approve", {
                "approval_id": approval_id,
                "request": "List authorized workspace entries",
                "session_id": "approval-session",
            }) as response:
                completed = json.loads(response.read().decode("utf-8"))

        self.assertEqual(pending["status"], "approval_required")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(
            completed["tool_results"][0]["result"]["entries"][0]["name"],
            "fixture.txt",
        )
        with store.connect() as database:
            statuses = [row[0] for row in database.execute(
                "SELECT status FROM approval_requests WHERE approval_id = ?",
                (approval_id,),
            )]
        self.assertEqual(statuses, ["consumed"])

    def test_api_status_is_non_probing_and_sse_exposes_only_event_metadata(self):
        status_code, status = self.get_json("/api/status")
        self.assertEqual(status_code, 200)
        self.assertEqual(status["provider_registry"]["default"], "test")
        self.assertEqual(status["providers"], {})

        with self.post_json("/api/request", {
            "request": "List authorized workspace entries",
            "session_id": "event-session",
        }) as response:
            self.assertEqual(response.status, 200)
            response.read()

        with urllib.request.urlopen(self.base_url + "/api/events?after=0", timeout=5) as response:
            lines = []
            while len(lines) < 30:
                line = response.readline().decode("utf-8")
                lines.append(line)
                if line.startswith("data: ") and "permission_decision" in line:
                    break
            stream = "".join(lines)
        self.assertIn("event: seed", stream)
        self.assertIn("permission_decision", stream)
        self.assertNotIn("details", stream)
        self.assertNotIn("temporary only", stream)

    def test_server_refuses_non_loopback_bind(self):
        with self.assertRaises(ValueError):
            create_server(self.application, host="0.0.0.0", port=0)


if __name__ == "__main__":
    import unittest

    unittest.main()