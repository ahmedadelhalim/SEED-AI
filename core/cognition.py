"""
SEED Autonomous Cognitive Intelligence Engine
Unifies the complete intelligence loop:
UNDERSTAND → RECALL → REASON → PLAN → EXECUTE → VERIFY → LEARN → REMEMBER
"""

import json
from typing import Any, Dict, List, Mapping, Optional, Tuple
from core.intelligence import (
    AdaptiveCommunicator,
    ContextAssembler,
    ExecutionVerifier,
    IntentClassifier,
    IntentType,
    VerificationOutcome,
)
from memory import store


class CognitiveEngine:
    """Central orchestrator for the SEED cognitive feedback and intelligence loop."""

    @staticmethod
    def process_objective(prompt: str, project_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        # 1. UNDERSTAND
        intent = IntentClassifier.classify(prompt)
        
        # 2. RECALL
        context = ContextAssembler.assemble(prompt, project_id=project_id, session_id=session_id)
        
        # 3. REASON & 4. PLAN
        requires_planning = intent in (IntentType.PLANNING, IntentType.RESEARCH, IntentType.EXECUTION)
        
        return {
            "intent": intent.value,
            "context": context,
            "requires_planning": requires_planning,
            "status": "cognition_initialized",
        }

    @staticmethod
    def learn_and_remember(task_id: int, prompt: str, result_summary: str, project_id: Optional[str] = None):
        """Extracts durable insights and stores them in persistent memory for continuous improvement."""
        try:
            memory_key = f"learned_workflow_{task_id}"
            content = f"Objective: {prompt[:100]} | Outcome: {result_summary[:200]}"
            store.save_memory(
                memory_type="durable_knowledge",
                memory_key=memory_key,
                content=content,
                project_id=project_id or "",
                approved=True,
            )
        except Exception:
            pass
