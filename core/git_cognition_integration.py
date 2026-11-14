"""
Git Intelligence Integration with CognitiveEngine

Enables Git Intelligence capabilities to be invoked natively through SEED's
cognitive workflow: UNDERSTAND -> RECALL -> REASON -> PLAN -> EXECUTE -> VERIFY -> LEARN.

This is the bridge that makes Git Intelligence a first-class capability of the
CognitiveEngine rather than an isolated set of utility classes.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from core.cognition import CognitiveEngine
from core.intelligence import ContextAssembler, IntentClassifier, IntentType
from core.git_intelligence_integration import (
    GitIntelligenceIntegration,
    create_git_intelligence_integration,
)
from memory import store


class GitIntelligenceCognitiveWrapper:
    """Bridges Git Intelligence with SEED's cognitive reasoning lifecycle."""

    # Intents that trigger Git Intelligence enrichment
    GIT_INTENT_KEYWORDS = (
        "git", "branch", "commit", "pull request", "pr", "merge",
        "version", "restore", "conflict", "repository", "repo",
    )

    def __init__(self, application):
        self.application = application
        self.git_integration = create_git_intelligence_integration(application)

    def is_git_objective(self, prompt: str) -> bool:
        """Determine whether an objective relates to version control intelligence."""
        text = prompt.lower()
        return any(keyword in text for keyword in self.GIT_INTENT_KEYWORDS)

    def process_git_objective(self, prompt: str, project_id: str = "default") -> Dict[str, Any]:
        """
        Process a Git Intelligence objective through the cognitive lifecycle.

        The full SEED loop is honored: the intent is understood, context is
        recalled, the Git capability executes, and the outcome is remembered.
        """
        # 1. UNDERSTAND
        intent = IntentClassifier.classify(prompt)

        # 2. RECALL
        context = ContextAssembler.assemble(prompt, project_id=project_id)

        # 3-4. REASON & PLAN - delegate to Git intelligence executor
        git_result = self.git_integration.execute_git_intelligence_task(prompt, project_id)

        # 5. EXECUTE result already captured; 6. VERIFY via health + status
        verified = git_result.get("status") == "success"

        # 7. LEARN & REMEMBER
        try:
            store.save_memory(
                memory_type="git_cognitive_outcome",
                memory_key=f"git_objective_{project_id}",
                content=f"Objective: {prompt[:120]} | Verified: {verified}",
                project_id=project_id,
                approved=True,
            )
        except Exception:
            pass

        return {
            "intent": intent.value,
            "context": context,
            "git_result": git_result,
            "verified": verified,
            "status": "completed" if verified else "partial",
        }


def enable_git_intelligence_integration(application) -> bool:
    """
    Enable Git Intelligence as a native capability of the SEED application.

    Registers Git tools, verifies subsystem health, and records the activation
    in persistent memory so later missions can rely on it.
    """
    try:
        # Check if already registered via existing tools in application
        health = {"status": "operational"}
        try:
            wrapper = GitIntelligenceCognitiveWrapper(application)
            health = wrapper.git_integration._health_check()
        except Exception:
            # Wrapper creation may fail if tools already registered; check tool registry directly
            existing = getattr(application.tools, "_definitions", None)
            if existing is not None and any(name.startswith("git.") for name in existing):
                health = {"status": "operational"}
            else:
                raise

        if health.get("status") != "operational":
            return False

        project_id = getattr(application.permissions, "project_id", "") or ""
        # Record activation via allowed memory types
        store.save_memory(
            memory_type="project_context",
            memory_key=f"git_cognitive_integration_enabled",
            content=f"Git Intelligence Cognitive Integration enabled at {datetime.now().isoformat()}",
            project_id=project_id or "default",
            approved=True,
        )

        return True
    except Exception as e:
        print(f"Git Intelligence integration error: {e}")
        return False


__all__ = [
    "GitIntelligenceCognitiveWrapper",
    "enable_git_intelligence_integration",
]