import argparse
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from core.application import SeedApplication
from security.approval_manager import ApprovalError, ApprovalExpiredError


DESKTOP_ROOT = Path(__file__).resolve().parents[1] / "desktop"
MAX_REQUEST_BYTES = 16 * 1024
MAX_TEXT_CHARS = 8000
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
STATIC_FILES = {
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


class SeedDesktopHTTPServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True
    allow_reuse_address = True

    def __init__(self, server_address, application):
        self.application = application
        self.csrf_token = secrets.token_urlsafe(32)
        self.event_stream_slots = threading.BoundedSemaphore(8)
        self.shutdown_event = threading.Event()
        self.handler_error_lock = threading.Lock()
        self.last_handler_error = None
        super().__init__(server_address, SeedDesktopRequestHandler)

    def shutdown(self):
        self.shutdown_event.set()
        super().shutdown()

    def handle_error(self, _request, _client_address):
        import sys

        error = sys.exc_info()[1]
        with self.handler_error_lock:
            self.last_handler_error = type(error).__name__ if error else "UnknownError"


class SeedDesktopRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "SEED-Desktop"
    sys_version = ""

    @property
    def application(self):
        return self.server.application

    def log_message(self, _format, *_args):
        return

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; style-src 'self'; "
            "script-src 'self'; img-src 'self' data:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        self.send_header("Cache-Control", "no-store")

    def _send_bytes(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()
        self.close_connection = True

    def _send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self._send_bytes(status, "application/json; charset=utf-8", body)

    def _host_allowed(self):
        host_header = self.headers.get("Host", "")
        try:
            parsed = urlsplit("//" + host_header)
            return parsed.hostname in ALLOWED_HOSTS and parsed.port == self.server.server_port
        except ValueError:
            return False

    def _same_origin(self):
        origin = self.headers.get("Origin", "")
        try:
            parsed = urlsplit(origin)
            return (
                parsed.scheme == "http"
                and parsed.hostname in ALLOWED_HOSTS
                and parsed.port == self.server.server_port
                and parsed.path in ("", "/")
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            return False

    def _request_json(self):
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise ValueError("JSON content type required")
        raw_length = self.headers.get("Content-Length", "")
        if not raw_length.isdigit():
            raise ValueError("Content length is required")
        length = int(raw_length)
        if length < 1 or length > MAX_REQUEST_BYTES:
            raise ValueError("Request size is invalid")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value

    def _drain_request_body(self):
        raw_length = self.headers.get("Content-Length", "0")
        if raw_length.isdigit():
            length = min(int(raw_length), MAX_REQUEST_BYTES)
            if length:
                self.rfile.read(length)

    def do_GET(self):
        if not self._host_allowed():
            self._send_json(403, {"error": "Local host required"})
            return

        parsed = urlsplit(self.path)
        if parsed.path == "/":
            try:
                html = (DESKTOP_ROOT / "index.html").read_text(encoding="utf-8")
            except OSError:
                self._send_json(503, {"error": "Desktop assets unavailable"})
                return
            html = html.replace("__SEED_CSRF_TOKEN__", self.server.csrf_token)
            self._send_bytes(200, "text/html; charset=utf-8", html.encode("utf-8"))
            return

        static_file = STATIC_FILES.get(parsed.path)
        if static_file is not None:
            filename, content_type = static_file
            try:
                body = (DESKTOP_ROOT / filename).read_bytes()
            except OSError:
                self._send_json(503, {"error": "Desktop assets unavailable"})
                return
            self._send_bytes(200, content_type, body)
            return

        if parsed.path == "/api/status":
            try:
                self._send_json(200, self.application.operations.status())
            except Exception:
                self._send_json(503, {"error": "Status is temporarily unavailable"})
            return

        if parsed.path == "/api/history":
            try:
                query = parse_qs(parsed.query)
                limit = min(max(int(query.get("limit", ["50"])[0]), 1), 100)
                self._send_json(200, {"tasks": self.application.operations.execution_history(limit)})
            except (TypeError, ValueError):
                self._send_json(400, {"error": "Invalid history query"})
            except Exception:
                self._send_json(503, {"error": "History is temporarily unavailable"})
            return

        if parsed.path == "/api/audit":
            try:
                query = parse_qs(parsed.query)
                limit = min(max(int(query.get("limit", ["100"])[0]), 1), 200)
                events = self.application.operations.recent_events(limit)
                metadata = [{
                    key: event[key]
                    for key in ("id", "task_id", "event_type", "created_at")
                } for event in events]
                self._send_json(200, {"events": metadata})
            except (TypeError, ValueError):
                self._send_json(400, {"error": "Invalid audit query"})
            except Exception:
                self._send_json(503, {"error": "Audit history is temporarily unavailable"})
            return

        if parsed.path == "/api/approvals":
            try:
                self._send_json(200, {
                    "approvals": self.application.operations.pending_approvals(limit=50)
                })
            except Exception:
                self._send_json(503, {"error": "Approvals are temporarily unavailable"})
            return

        if parsed.path.startswith("/api/sessions/"):
            session_id = parsed.path.rsplit("/", 1)[-1]
            if not session_id or len(session_id) > 80:
                self._send_json(400, {"error": "Invalid session ID"})
                return
            try:
                from memory import store

                messages = store.get_session_messages(session_id, limit=100)
                visible = [message for message in messages if message.get("role") in {"user", "assistant"}]
                self._send_json(200, {"messages": visible})
            except Exception:
                self._send_json(503, {"error": "Session is temporarily unavailable"})
            return

        if parsed.path == "/api/memory":
            try:
                from memory import store
                with store.connect() as db:
                    rows = db.execute("SELECT memory_type, memory_key, content, project_id, approved, created_at, updated_at FROM memory_items ORDER BY updated_at DESC LIMIT 100").fetchall()
                    items = [dict(row) for row in rows]
                self._send_json(200, {"memory_items": items})
            except Exception:
                self._send_json(503, {"error": "Memory is temporarily unavailable"})
            return

        if parsed.path == "/api/events":
            self._stream_events(parsed.query)
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._host_allowed() or not self._same_origin():
            self._drain_request_body()
            self._send_json(403, {"error": "Same-origin localhost request required"})
            return
        if self.headers.get("X-SEED-CSRF") != self.server.csrf_token:
            # Consume the request body before closing the response so clients do
            # not observe a connection reset when a CSRF check rejects a POST.
            self._drain_request_body()
            self._send_json(403, {"error": "Request verification failed"})
            return

        try:
            payload = self._request_json()
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "Invalid request body"})
            return

        parsed = urlsplit(self.path)
        if parsed.path == "/api/plan":
            objective = payload.get("objective")
            if not isinstance(objective, str) or not objective.strip() or len(objective) > MAX_TEXT_CHARS:
                self._send_json(400, {"error": "Planning objective is invalid"})
                return
            try:
                generated = self.application.orchestrator.generate_live_plan(objective)
                self._send_json(200, generated)
            except Exception as error:
                self._send_json(422, {"error": "Plan validation failed", "reason": str(error)})
            return

        if parsed.path == "/api/plan/execute":
            plan_id = payload.get("plan_id")
            if not isinstance(plan_id, str) or not plan_id:
                self._send_json(400, {"error": "Plan ID is invalid"})
                return
            try:
                task = self.application.tasks.submit("Execute plan " + plan_id)
                result = self.application.orchestrator.execute_plan(plan_id, task["task_id"])
                self._send_json(200, result)
            except Exception as error:
                self._send_json(422, {"error": "Plan execution failed", "reason": str(error)})
            return

        if parsed.path == "/api/request":
            user_request = payload.get("request")
            session_id = payload.get("session_id")
            approval_id = payload.get("approval_id")
            if not isinstance(user_request, str) or not user_request.strip() or len(user_request) > MAX_TEXT_CHARS:
                self._send_json(400, {"error": "Request text is invalid"})
                return
            if session_id is not None and (not isinstance(session_id, str) or len(session_id) > 80):
                self._send_json(400, {"error": "Session ID is invalid"})
                return
            try:
                result = self.application.seed_request(
                    user_request,
                    session_id=session_id,
                    approval_id=approval_id if isinstance(approval_id, str) else None,
                )
                self._send_json(200, {
                    "task_id": result.task_id,
                    "session_id": result.session_id,
                    "status": result.status,
                    "response": result.response,
                    "steps": result.steps,
                    "tool_results": list(result.tool_results),
                    "pending_approvals": list(result.pending_approvals),
                })
            except Exception:
                self._send_json(503, {"error": "SEED could not process the request"})
            return

        if parsed.path == "/api/approvals/approve":
            approval_id = payload.get("approval_id")
            user_request = payload.get("request")
            session_id = payload.get("session_id")
            if not isinstance(approval_id, str) or not approval_id or len(approval_id) > 80:
                self._send_json(400, {"error": "Approval ID is invalid"})
                return
            if not isinstance(user_request, str) or not user_request.strip() or len(user_request) > MAX_TEXT_CHARS:
                self._send_json(400, {"error": "Request text is invalid"})
                return
            if not isinstance(session_id, str) or not session_id or len(session_id) > 80:
                self._send_json(400, {"error": "Session ID is invalid"})
                return
            try:
                self.application.orchestrator.approvals.approve(
                    approval_id, approved_by="desktop-local-user"
                )
                result = self.application.seed_request(
                    user_request,
                    session_id=session_id,
                    approval_id=approval_id,
                )
                self._send_json(200, {
                    "task_id": result.task_id,
                    "session_id": result.session_id,
                    "status": result.status,
                    "response": result.response,
                    "steps": result.steps,
                    "tool_results": list(result.tool_results),
                    "pending_approvals": list(result.pending_approvals),
                })
            except ApprovalExpiredError:
                self._send_json(410, {"error": "Approval expired; request a new plan"})
            except ApprovalError:
                self._send_json(409, {"error": "Approval is no longer available"})
            except Exception:
                self._send_json(503, {"error": "SEED could not resume the approved request"})
            return

        if parsed.path == "/api/plan/status":
            plan_id = payload.get("plan_id")
            try:
                self._send_json(200, self.application.orchestrator.plan_engine.status(plan_id))
            except Exception:
                self._send_json(404, {"error": "Plan is unavailable"})
            return

        if parsed.path == "/api/plan/resume":
            plan_id = payload.get("plan_id")
            try:
                self._send_json(200, self.application.orchestrator.plan_engine.resume(plan_id))
            except Exception:
                self._send_json(422, {"error": "Plan resume failed"})
            return

        if parsed.path == "/api/plan/cancel":
            plan_id = payload.get("plan_id")
            try:
                self._send_json(200, {"plan_id": plan_id, "state": self.application.orchestrator.plan_engine.cancel(plan_id)})
            except Exception:
                self._send_json(422, {"error": "Plan cancellation failed"})
            return

        self._send_json(404, {"error": "Not found"})

    def _stream_events(self, query_string):
        if not self.server.event_stream_slots.acquire(blocking=False):
            self._send_json(503, {"error": "Event stream capacity reached"})
            return
        try:
            query = parse_qs(query_string)
            cursor_value = self.headers.get("Last-Event-ID", query.get("after", ["0"])[0])
            cursor = max(int(cursor_value), 0)
        except (TypeError, ValueError):
            self.server.event_stream_slots.release()
            self._send_json(400, {"error": "Invalid event cursor"})
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Connection", "close")
        self._security_headers()
        self.end_headers()
        self.close_connection = True
        last_heartbeat = 0
        try:
            while not self.server.shutdown_event.is_set():
                events = self.application.operations.events_after(cursor, limit=100)
                for event in events:
                    event_id = int(event["id"])
                    payload = {
                        "event_id": event_id,
                        "task_id": event["task_id"],
                        "event_type": event["event_type"],
                        "created_at": event["created_at"],
                        "decision": event.get("decision"),
                        "state": _presentation_state(
                            event["event_type"], event.get("decision")
                        ),
                    }
                    frame = (
                        "id: " + str(event_id) + "\n"
                        "event: seed\n"
                        "data: " + json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
                        + "\n\n"
                    )
                    self.wfile.write(frame.encode("utf-8"))
                    cursor = event_id
                now = time.monotonic()
                if now - last_heartbeat >= 10:
                    self.wfile.write(b": keepalive\n\n")
                    last_heartbeat = now
                self.wfile.flush()
                time.sleep(0.35)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.server.event_stream_slots.release()


def _presentation_state(event_type, decision=None):
    if event_type == "permission_decision":
        return {
            "ALLOW": "executing",
            "DENY": "error",
            "REQUIRE_APPROVAL": "awaiting_approval",
        }.get(decision, "processing")
    return {
        "task_created": "processing",
        "orchestration_started": "processing",
        "tool_completed": "executing",
        "workspace_listed": "executing",
        "approval_required": "awaiting_approval",
        "response_completed": "responding",
        "tool_denied": "error",
        "tool_rejected": "error",
        "tool_failed": "error",
        "model_request_failed": "error",
        "workspace_access_denied": "error",
    }.get(event_type, "processing")


def create_server(application=None, host="127.0.0.1", port=8765):
    if host not in ALLOWED_HOSTS:
        raise ValueError("Desktop server must bind to loopback")
    if host == "localhost":
        host = "127.0.0.1"
    app = application or SeedApplication()
    if "desktop-http" not in app.services:
        app.services.register("desktop-http", "transport")
    return SeedDesktopHTTPServer((host, port), app)


def main():
    parser = argparse.ArgumentParser(description="Run the SEED localhost control center")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    server = create_server(port=arguments.port)
    print("SEED desktop control center: http://127.0.0.1:" + str(server.server_port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
