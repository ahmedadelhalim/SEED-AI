
from runtime.agent_runtime import AgentRuntime

agent = AgentRuntime()

print("TEST: Workspace traversal")
result = agent.list_workspace("../Windows")

print("RESULT:", result)

assert result["status"] == "denied", (
    "SECURITY FAILURE: Outside path was not denied"
)

print("WORKSPACE_ESCAPE_BLOCKED")
