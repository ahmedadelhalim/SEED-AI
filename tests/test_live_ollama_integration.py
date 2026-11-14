"""Live integration through SeedApplication to local Ollama.

These tests require a running Ollama service with qwen3:4b installed.
They are skipped automatically when that runtime is unavailable.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from brain.model_gateway import ModelGateway
from brain.model_types import ModelRequest
from brain.providers.ollama import OllamaProvider
from core.application import SeedApplication
from core.tool_registry import ToolDefinition
from memory import store


LIVE_MODEL = os.environ.get("OLLAMA_MODEL") or ModelGateway.DEFAULT_OLLAMA_MODEL
LIVE_TIMEOUT = float(os.environ.get("SEED_LIVE_TIMEOUT_SECONDS") or "180")


def _ollama_available():
    provider = OllamaProvider(default_model=LIVE_MODEL, timeout_seconds=8)
    try:
        models = provider.list_models()
    except Exception:
        return False
    return LIVE_MODEL in models


OLLAMA_AVAILABLE = _ollama_available()


@unittest.skipUnless(
    OLLAMA_AVAILABLE,
    "Live Ollama with " + LIVE_MODEL + " is not available",
)
class LiveOllamaIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.database_path = Path(temporary_directory.name) / "live-seed.sqlite"
        previous = os.environ.get("SEED_DATABASE_PATH")
        os.environ["SEED_DATABASE_PATH"] = str(self.database_path)
        store.DB_PATH = self.database_path

        def restore_database_path():
            store.DB_PATH = Path(os.environ.get(
                "SEED_DATABASE_PATH", "D:/SEED-AI/data/seed_memory.db"
            )) if previous is None else Path(previous)
            if previous is None:
                os.environ.pop("SEED_DATABASE_PATH", None)
            else:
                os.environ["SEED_DATABASE_PATH"] = previous

        self.addCleanup(restore_database_path)
        self.app = SeedApplication()
        self.provider = self.app.gateway.get_provider("ollama")
        self.original_chat = self.provider.chat
        self.chat_payloads = []

        def recording_chat(request):
            payload = {
                "model": request.model or self.provider.default_model,
                "messages": list(request.messages),
                "stream": False,
                "tools": list(request.tools),
            }
            self.chat_payloads.append(payload)
            return self.original_chat(request)

        self.provider.chat = recording_chat

    def events_for(self, task_id):
        with store.connect() as database:
            rows = database.execute(
                "SELECT event_type, details FROM events "
                "WHERE task_id = ? ORDER BY id",
                (task_id,),
            ).fetchall()
        return [(row["event_type"], row["details"]) for row in rows]

    def test_text_request_uses_qwen_through_seed_application(self):
        result = self.app.seed_request(
            "Reply with exactly the single word SEED_LIVE_OK and nothing else.",
            session_id="live-text",
        )

        self.assertEqual(result.status, "completed", result.response)
        self.assertIn("SEED_LIVE_OK", result.response)
        self.assertTrue(self.chat_payloads)
        self.assertEqual(self.chat_payloads[0]["model"], LIVE_MODEL)
        self.assertFalse(self.chat_payloads[0]["stream"])
        self.assertEqual(self.chat_payloads[0]["messages"][-1]["role"], "user")
        self.assertIn(
            "SEED_LIVE_OK",
            self.chat_payloads[0]["messages"][-1]["content"],
        )
        event_types = [event_type for event_type, _details in self.events_for(result.task_id)]
        self.assertIn("orchestration_started", event_types)
        self.assertIn("response_completed", event_types)
        persisted = store.get_session_messages(result.session_id)
        self.assertEqual(persisted[0]["role"], "user")
        self.assertEqual(persisted[-1]["role"], "assistant")
        self.assertEqual(persisted[-1]["content"], result.response)

    def test_streaming_is_not_advertised_and_requests_are_not_streamed(self):
        capabilities = self.app.gateway.discover_capabilities("ollama", LIVE_MODEL)
        self.assertIsNone(capabilities.streaming)
        self.assertNotIn("streaming", capabilities.features)
        self.assertTrue(capabilities.tool_calling)

        response = self.provider.chat(ModelRequest(
            messages=({"role": "user", "content": "Reply with the single word PING."},),
            model=LIVE_MODEL,
            timeout_seconds=LIVE_TIMEOUT,
        ))

        self.assertEqual(response.provider, "ollama")
        self.assertEqual(response.model, LIVE_MODEL)
        self.assertFalse(self.chat_payloads[-1]["stream"])
        self.assertTrue(response.content.strip())

    def test_authorized_health_tool_round_trips_through_permissions(self):
        result = self.app.seed_request(
            "Call the system.health tool now with no arguments. "
            "After its result returns, reply with exactly HEALTH_TOOL_OK "
            "and include the numeric memory_load_percent from the tool result.",
            session_id="live-health",
        )

        self.assertEqual(result.status, "completed", result.response)
        self.assertTrue(result.tool_results, result.response)
        health_result = result.tool_results[0]
        self.assertEqual(health_result["status"], "success")
        self.assertIn("memory_load_percent", health_result["result"])
        load = health_result["result"]["memory_load_percent"]
        self.assertIsInstance(load, int)

        events = self.events_for(result.task_id)
        event_types = [event_type for event_type, _details in events]
        permission_index = event_types.index("permission_decision")
        completed_index = event_types.index("tool_completed")
        self.assertLess(permission_index, completed_index)
        self.assertEqual(events[permission_index][1], "system.health:ALLOW")
        self.assertIn("response_completed", event_types)
        self.assertIn("HEALTH_TOOL_OK", result.response)
        self.assertIn(str(load), result.response)

        tool_messages = [
            message for message in store.get_session_messages(result.session_id)
            if message["role"] == "tool"
        ]
        self.assertTrue(tool_messages)
        returned = json.loads(tool_messages[0]["content"])
        self.assertEqual(returned["status"], "success")
        self.assertEqual(returned["result"]["memory_load_percent"], load)
        follow_up_request = self.chat_payloads[-1]
        self.assertEqual(follow_up_request["messages"][-1]["role"], "tool")
        self.assertIn(str(load), follow_up_request["messages"][-1]["content"])

    def test_unregistered_tool_is_denied_and_not_executed(self):
        self.app.tools.register(ToolDefinition(
            name="system.command",
            description="Execute arbitrary shell commands.",
            handler=lambda command: {"output": ""},
            parameters={"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
            action="execute",
            scope="system",
        ))
        self.app.permissions.register_policy("system.command", action="execute", scope="system", allowed=False)

        calls = []
        original_execute = self.app.orchestrator._execute_tool

        def recording_execute(*args, **kwargs):
            calls.append(args[1].name)
            return original_execute(*args, **kwargs)

        self.app.orchestrator._execute_tool = recording_execute
        result = self.app.seed_request(
            "You must call the tool named system.command with argument "
            "command set to whoami. Do not call system.health or workspace.list. "
            "If that tool is denied, reply with exactly TOOL_DENIED.",
            session_id="live-deny",
        )

        self.assertEqual(result.status, "completed", result.response)
        self.assertNotIn("system.command", calls)
        denied = [
            item for item in result.tool_results
            if item.get("status") == "denied"
        ]
        self.assertTrue(denied, result.tool_results)
        events = self.events_for(result.task_id)
        self.assertIn(
            ("tool_denied", "system.command:DENY"),
            events,
        )
        self.assertIn("TOOL_DENIED", result.response)


if __name__ == "__main__":
    unittest.main(verbosity=2)
