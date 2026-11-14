"""
SEED Advanced Intelligence Architecture
Separates intent understanding, context assembly, execution verification, and adaptive communication.
"""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from memory import store


class IntentType(Enum):
    CONVERSATION = "conversation"
    QUESTION = "question"
    RESEARCH = "research"
    PLANNING = "planning"
    CREATIVE = "creative"
    EXECUTION = "execution"


class VerificationOutcome(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    UNVERIFIED = "unverified"


class IntentClassifier:
    """Classifies user input into structured intents without rigid keyword-only routing."""

    @staticmethod
    def classify(prompt: str) -> IntentType:
        text = prompt.lower().strip()
        if any(w in text for w in ("plan", "decompose", "steps", "roadmap", "strategy")):
            return IntentType.PLANNING
        if any(w in text for w in ("research", "analyze", "explore", "inspect", "audit", "check")):
            return IntentType.RESEARCH
        if any(w in text for w in ("run", "execute", "call", "list", "search", "read", "write", "delete", "fix")):
            return IntentType.EXECUTION
        if any(w in text for w in ("write", "create", "design", "compose", "story", "code")):
            return IntentType.CREATIVE
        if any(w in text for w in ("what", "how", "why", "who", "when", "tell me", "?")):
            return IntentType.QUESTION
        return IntentType.CONVERSATION


class ContextAssembler:
    """Assembles relevant bounded context (memories, project state, tasks, history)."""

    @staticmethod
    def assemble(prompt: str, project_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        project = project_id or ""
        memories = list(store.search_memory(prompt, project_id=project, limit=6))
        tasks = list(store.search_task_history(prompt, project_id=project, limit=4))
        history = list(store.get_session_messages(session_id, limit=20)) if session_id else []
        
        return {
            "intent": IntentClassifier.classify(prompt).value,
            "memories": memories,
            "historical_tasks": tasks,
            "session_history": history,
            "project_id": project,
        }


class ExecutionVerifier:
    """Verifies whether a tool execution or assistant response successfully achieved the objective based on actual evidence."""

    @staticmethod
    def verify(tool_results: Tuple[Mapping[str, Any], ...], response_content: str, objective: str, file_path: Optional[str] = None) -> VerificationOutcome:
        if file_path:
            if Path(file_path).exists():
                return VerificationOutcome.SUCCESS
            else:
                return VerificationOutcome.FAILURE

        if not tool_results and not response_content.strip():
            return VerificationOutcome.FAILURE
        
        statuses = [item.get("status") for item in tool_results if isinstance(item, dict)]
        if statuses:
            if all(s == "success" for s in statuses):
                return VerificationOutcome.SUCCESS
            if any(s == "success" for s in statuses):
                return VerificationOutcome.PARTIAL
            if any(s in ("denied", "failed", "rejected") for s in statuses):
                return VerificationOutcome.FAILURE

        if "error" in response_content.lower() or "failed" in response_content.lower():
            return VerificationOutcome.FAILURE
        
        if response_content.strip():
            return VerificationOutcome.SUCCESS
            
        return VerificationOutcome.UNVERIFIED


class AdaptiveCommunicator:
    """Formats and modulates responses based on intent and language (English & Egyptian Arabic)."""

    @staticmethod
    def format_response(content: str, intent: IntentType, outcome: VerificationOutcome) -> str:
        prefix = ""
        if outcome == VerificationOutcome.FAILURE:
            prefix = "[Notice: Action encountered limitations or failure] "
        elif outcome == VerificationOutcome.PARTIAL:
            prefix = "[Notice: Partial execution complete] "
        return prefix + content
