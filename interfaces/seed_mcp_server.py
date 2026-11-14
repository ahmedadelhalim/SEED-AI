from typing import Optional
import threading

from core.application import SeedApplication
from mcp.server import MCPServer

server = MCPServer(
    name="SEED-AI",
    version="0.1.0",
    instructions=(
        "SEED is the central orchestrator. Send user objectives through "
        "seed_request; SEED selects models, retrieves context, authorizes tools, "
        "and records outcomes. workspace_list is a low-level SEED tool."
    ),
)

_application = None
_application_lock = threading.Lock()


def get_application() -> SeedApplication:
    global _application
    if _application is None:
        with _application_lock:
            if _application is None:
                _application = SeedApplication()
    return _application


def workspace_list(relative_path: str = ".") -> dict:
    """List names and types of entries inside the authorized SEED workspace."""
    return get_application().tool_adapter.invoke(
        "workspace.list", {"relative_path": relative_path}
    )


def seed_request(user_request: str, session_id: Optional[str] = None) -> dict:
    """Submit a user objective to SEED's central orchestration lifecycle."""
    result = get_application().seed_request(user_request, session_id=session_id)
    return {
        "task_id": result.task_id,
        "session_id": result.session_id,
        "status": result.status,
        "response": result.response,
        "steps": result.steps,
        "tool_results": list(result.tool_results),
        "pending_approvals": list(result.pending_approvals),
    }


def create_plan(objective: str) -> dict:
    return get_application().orchestrator.generate_live_plan(objective)


def execute_plan(plan_id: str) -> dict:
    task = get_application().tasks.submit("Execute plan " + plan_id)
    return get_application().orchestrator.execute_plan(plan_id, task["task_id"])


def plan_status(plan_id: str) -> dict:
    return get_application().orchestrator.plan_engine.status(plan_id)


def resume_plan(plan_id: str) -> dict:
    return get_application().orchestrator.plan_engine.resume(plan_id)


def cancel_plan(plan_id: str) -> dict:
    return {"plan_id": plan_id, "state": get_application().orchestrator.plan_engine.cancel(plan_id)}


server.add_tool(
    workspace_list,
    name="workspace_list",
    description="List files and directories inside the authorized SEED workspace.",
)
server.add_tool(
    seed_request,
    name="seed_request",
    description="Submit a user objective to SEED for planning, governed tool execution, and a final response.",
)
server.add_tool(
    create_plan,
    name="create_plan",
    description="Create and validate a SEED plan without executing it.",
)
server.add_tool(
    execute_plan,
    name="execute_plan",
    description="Execute a previously validated SEED plan through central governance.",
)
server.add_tool(plan_status, name="plan_status", description="Read a persisted SEED plan status.")
server.add_tool(resume_plan, name="resume_plan", description="Resume a persisted SEED plan safely.")
server.add_tool(cancel_plan, name="cancel_plan", description="Cancel pending and running steps of a SEED plan.")


if __name__ == "__main__":
    get_application()
    server.run(transport="stdio")
