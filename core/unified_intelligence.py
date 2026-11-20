"""
Unified Intelligence Layer for SEED-AI.

This module provides the single, central intelligence orchestration for the full
UNDERSTAND -> RECALL -> REASON -> PLAN -> DECIDE -> EXECUTE -> VERIFY -> LEARN -> REMEMBER
cognitive loop. It composes:

- core.cognition.CognitiveEngine (intent classification, context assembly, verification, learning)
- core.git_intelligence (branching, commits, PRs, versioning)
- core.project_discovery (project understanding)
- core.engineering_intelligence (engineering analysis)
- core.orchestrator (execution)
- core.plan_engine (plan state)
- memory.store (persistent memory)

The goal is to have ONE coherent intelligence pipeline rather than scattered,
independent subsystems that may drift in behavior.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from core.cognition import (
    AdaptiveCommunicator,
    ContextAssembler,
    ExecutionVerifier,
    IntentClassifier,
    IntentType,
    VerificationOutcome,
)
from memory import store


class CognitiveStage(str, Enum):
    UNDERSTAND = "understand"
    RECALL = "recall"
    REASON = "reason"
    PLAN = "plan"
    DECIDE = "decide"
    EXECUTE = "execute"
    VERIFY = "verify"
    LEARN = "learn"
    REMEMBER = "remember"


class UnifiedIntelligenceConfig:
    """Tunables for the unified cognitive loop."""

    def __init__(
        self,
        max_recall_memories: int = 6,
        max_historical_tasks: int = 4,
        max_context_tasks: int = 4,
        session_history_limit: int = 20,
        git_intent_confidence: float = 0.7,
        max_executions_per_objective: int = 3,
        plan_revision_limit: int = 5,
        enable_self_memory_updates: bool = True,
    ):
        self.max_recall_memories = max_recall_memories
        self.max_historical_tasks = max_historical_tasks
        self.max_context_tasks = max_context_tasks
        self.session_history_limit = session_history_limit
        self.git_intent_confidence = git_intent_confidence
        self.max_executions_per_objective = max_executions_per_objective
        self.plan_revision_limit = plan_revision_limit
        self.enable_self_memory_updates = enable_self_memory_updates


class UnifiedIntelligenceEngine:
    """
    The single orchestrator for SEED's cognitive loop.

    Coordinates the lower-level engines (CognitiveEngine pieces, Git intelligence,
    ProjectDiscovery, EngineeringIntelligence, PlanEngine, Orchestrator) into one
    cohesive UNDERSTAND -> ... -> REMEMBER pipeline for each user objective.
    """

    def __init__(
        self,
        application=None,
        memory_store=None,
        config: Optional[UnifiedIntelligenceConfig] = None,
    ):
        self.memory_store = memory_store or store
        self.config = config or UnifiedIntelligenceConfig()
        self.application = application
        self.stage_history: List[CognitiveStage] = []

    # ------------------------------------------------------------------
    # UNDERSTAND
    # ------------------------------------------------------------------
    def understand(self, prompt: str, project_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        intent = IntentClassifier.classify(prompt)
        if self._looks_like_git_objective(prompt):
            intent = IntentType.EXECUTION  # Git objectives route through execution pipeline
        return {
            "raw_prompt": prompt,
            "intent": intent,
            "stage": CognitiveStage.UNDERSTAND,
            "classified_at": self._now_iso(),
        }

    def _looks_like_git_objective(self, prompt: str) -> bool:
        text = prompt.lower()
        git_markers = ("git ", "branch", "commit", "pull request", "pr ", "conflict", "version", "restoration")
        return any(marker in text for marker in git_markers)

    # ------------------------------------------------------------------
    # RECALL
    # ------------------------------------------------------------------
    def recall(self, prompt: str, project_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        context = ContextAssembler.assemble(
            prompt,
            project_id=project_id,
            session_id=session_id,
        )
        self.stage_history.append(CognitiveStage.RECALL)
        return {
            "context": context,
            "stage": CognitiveStage.RECALL,
            "recalled_memories": len(context.get("memories") or []),
            "historical_tasks": len(context.get("historical_tasks") or []),
        }

    # ------------------------------------------------------------------
    # REASON
    # ------------------------------------------------------------------
    def reason(self, prompt: str, git_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Reasoned analysis: decompose into subgoals / requirements when possible.
        # Now delegates to ModelGateway for actual LLM inference when available.
        analysis = None
        if self.application is not None:
            try:
                engineering = self.application.engineering_intelligence
                if engineering is not None:
                    analysis = engineering.analyze_codebase(
                        requirements=[prompt],
                        project_id=None,
                    )
            except Exception:
                analysis = None

        # Invoke LLM via ModelGateway for reasoning
        from brain.model_gateway import ModelGateway
        from brain.model_types import ModelRequest

        gateway = ModelGateway.with_local_defaults()

        # Build a ModelRequest with appropriate messages
        request = ModelRequest(
            messages=({"role": "user", "content": prompt},),
            model=None,  # Let gateway use default
            temperature=0.7,
            timeout_seconds=120,
            provider="ollama",
        )

        try:
            response = gateway.complete(request)
            llm_insights = response.content
        except Exception as e:
            llm_insights = f"LLM invocation failed: {e}"
            analysis = None

        subgoals: List[str] = []
        if analysis is not None:
            for requirement in (analysis.get("requirements") or []):
                subgoals.append(str(requirement.get("description") or requirement))
        # Always include at least the original prompt as a subgoal
        if not subgoals:
            subgoals.append(prompt.strip())

        # Merge LLM insights into subgoals if available
        if llm_insights and not llm_insights.startswith("LLM invocation failed"):
            # Extract key points from LLM response to form subgoals
            key_lines = [line.strip() for line in llm_insights.split('\n')
                        if line.strip() and not line.startswith('Okay')
                        and not line.startswith('Hmm')
                        and not line.startswith('First')]
            if key_lines:
                subgoals.extend(key_lines[:4])  # Limit to 4 key insights

        self.stage_history.append(CognitiveStage.REASON)
        return {
            "subgoals": subgoals,
            "insights": analysis.get("insights") if analysis else [],
            "llm_response": llm_insights if llm_insights else None,
            "stage": CognitiveStage.REASON,
        }

    # ------------------------------------------------------------------
    def plan(self, subgoals: List[str], project_id: Optional[str] = None) -> Dict[str, Any]:
        plan_id = None
        steps = [
            {"step_id": f"step-{index}", "name": goal}
            for index, goal in enumerate(subgoals, 1)
        ] or [{"step_id": "step-1", "name": "Execute objective"}]
        if self.application is not None and self.application.plan_engine is not None:
            try:
                plan_id = self.application.plan_engine.create_plan(
                    objective=" ".join(subgoals),
                    steps=steps,
                )
            except Exception:
                plan_id = None

        self.stage_history.append(CognitiveStage.PLAN)
        return {
            "plan_id": plan_id,
            "steps": steps,
            "stage": CognitiveStage.PLAN,
        }

    # ------------------------------------------------------------------
    # DECIDE
    # ------------------------------------------------------------------
    def decide(self, prompt: str, git_intelligence: bool = False) -> Dict[str, Any]:
        # Decide: pick next action given reasoning + plan state.
        action = "proceed"
        if git_intelligence:
            action = "git_intelligence_workflow"
        elif self.stage_history and self.stage_history[-1] == CognitiveStage.PLAN:
            action = "execute_plan"
        self.stage_history.append(CognitiveStage.DECIDE)
        return {
            "action": action,
            "stage": CognitiveStage.DECIDE,
            "prompt": prompt,
        }

    # ------------------------------------------------------------------
    # EXECUTE
    # ------------------------------------------------------------------
    def execute(self, objective: str, session_id: Optional[str] = None, identity=None) -> Dict[str, Any]:
        from core.orchestrator import SeedOrchestrator
        from core.task_engine import TaskEngine
        from core.tool_registry import ToolRegistry
        from security.permission_engine import PermissionEngine
        from brain.model_gateway import ModelGateway

        # When running standalone (no SeedApplication), build real-but-empty
        # registries so the orchestrator never receives ``None``.
        gateway = self.application.gateway if self.application is not None else ModelGateway.with_local_defaults()
        tools = self.application.tools if self.application is not None else ToolRegistry()
        permissions = self.application.permissions if self.application is not None else PermissionEngine()
        tasks = self.application.tasks if self.application is not None else TaskEngine()

        orchestrator = SeedOrchestrator(
            gateway=gateway,
            tools=tools,
            permissions=permissions,
            tasks=tasks,
        )
        try:
            result = orchestrator.run(
                objective,
                session_id=session_id,
                identity=identity,
            )
            status = result.status
            response = result.response
            steps = result.steps
            tool_results = list(getattr(result, "tool_results", ()) or ())
        except Exception as exc:
            status = "failed"
            response = f"{type(exc).__name__}: {exc}"
            steps = 0
            tool_results = []

        self.stage_history.append(CognitiveStage.EXECUTE)
        return {
            "orchestrator_status": status,
            "response": response,
            "steps": steps,
            "tool_results": tool_results,
            "stage": CognitiveStage.EXECUTE,
        }

    # ------------------------------------------------------------------
    # VERIFY
    # ------------------------------------------------------------------
    def verify(self, execution_result: Dict[str, Any], objective: str) -> VerificationOutcome:
        # Delegate to the canonical ExecutionVerifier.
        outcome = ExecutionVerifier.verify(
            tool_results=tuple(execution_result.get("tool_results") or ()),
            response_content=str(execution_result.get("response") or ""),
            objective=objective,
            file_path=execution_result.get("file_path"),
        )
        self.stage_history.append(CognitiveStage.VERIFY)
        return outcome

    # ------------------------------------------------------------------
    # LEARN
    # ------------------------------------------------------------------
    def learn(self, prompt: str, verification_outcome: VerificationOutcome, execution_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        learning_entry = None
        if self.config.enable_self_memory_updates:
            # Store learned knowledge from the interaction.
            key = f"learned:{prompt.strip()[:60]}"
            learning_entry = {
                "memory_type": "durable_knowledge",
                "memory_key": key,
                "content": f"Objective resolved with outcome={verification_outcome.value} via SEED. Response: {str((execution_result or {}).get('response', ''))[:300]}",
                "source_task_id": None,
                "approved": True,
            }
            try:
                self.memory_store.save_memory(
                    memory_type=learning_entry["memory_type"],
                    memory_key=learning_entry["memory_key"],
                    content=learning_entry["content"],
                    project_id=None,
                    approved=True,
                    source_task_id=None,
                )
            except Exception:
                learning_entry = None

        self.stage_history.append(CognitiveStage.LEARN)
        return {
            "learned": learning_entry is not None,
            "stage": CognitiveStage.LEARN,
        }

    # ------------------------------------------------------------------
    # REMEMBER
    # ------------------------------------------------------------------
    def remember(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        entry = None
        if self.config.enable_self_memory_updates:
            entry = {
                "memory_type": "durable_knowledge",
                "memory_key": f"objective:{prompt.strip()[:60]}",
                "content": f"Resolved objective: {prompt.strip()[:300]}",
                "source_task_id": None,
                "approved": True,
            }
            try:
                self.memory_store.save_memory(
                    memory_type=entry["memory_type"],
                    memory_key=entry["memory_key"],
                    content=entry["content"],
                    project_id=None,
                    approved=True,
                    source_task_id=None,
                )
            except Exception:
                entry = None

        self.stage_history.append(CognitiveStage.REMEMBER)
        return {
            "remembered": entry is not None,
            "stage": CognitiveStage.REMEMBER,
        }

    # ------------------------------------------------------------------
    # Full unified loop
    # ------------------------------------------------------------------
    def process_objective(self, prompt: str, project_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Run one complete UNDERSTAND -> RECALL -> REASON -> PLAN -> DECIDE -> EXECUTE -> VERIFY -> LEARN -> REMEMBER cycle.
        """
        self.stage_history = []

        understood = self.understand(prompt, project_id=project_id, session_id=session_id)
        recalled = self.recall(prompt, project_id=project_id, session_id=session_id)
        reasoning = self.reason(prompt, git_context=None)
        planning = self.plan(reasoning.get("subgoals") or [prompt], project_id=project_id)
        decision = self.decide(prompt, git_intelligence=self._looks_like_git_objective(prompt))
        execution = self.execute(
            " ".join(reasoning.get("subgoals") or [prompt]),
            session_id=session_id,
        ) if decision.get("action") == "execute_plan" or decision.get("action") == "git_intelligence_workflow" else {
            "orchestrator_status": "skipped",
            "response": "",
            "steps": 0,
        }
        verification_outcome = self.verify(execution, " ".join(reasoning.get("subgoals") or [prompt]))
        learning = self.learn(prompt, verification_outcome, execution)
        remembering = self.remember(prompt, context=recalled)

        return {
            "prompt": prompt,
            "stages_completed": [stage.value for stage in self.stage_history],
            "result": {
                "understood": understood,
                "recalled": recalled,
                "reasoning": reasoning,
                "planning": planning,
                "decision": decision,
                "execution": execution,
                "verification_outcome": verification_outcome.value,
                "learning": learning,
                "remembering": remembering,
            },
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _now_iso() -> str:
        import datetime
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    def reset_stages(self):
        self.stage_history = []
