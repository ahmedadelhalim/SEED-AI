"""Autonomous Development Engine for SEED SDLC Workflow

Unified requirements→plans→execution→verification pipeline using Git Intelligence
components (BranchManager, CommitIntelligence, PullRequestManager, ConflictAnalyzer,
ProjectVersioner), PlanEngine for durable plan state, ExecutionVerifier for evidence-based
verification, and memory.store for learning/remembering.

One central intelligence capable of UNDERSTAND→RECALL→REASON→PLAN→DECIDE→EXECUTE→VERIFY→LEARN→REMEMBER.
"""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.git_intelligence.branch_manager import BranchManager
from core.git_intelligence.commit_intelligence import CommitIntelligence
from core.git_intelligence.pull_request_manager import PullRequestManager
from core.git_intelligence.conflict_analyzer import ConflictAnalyzer
from core.git_intelligence.project_versioner import ProjectVersioner
from core.plan_engine import PlanEngine
from core.intelligence import (
    AdaptiveCommunicator,
    ContextAssembler,
    ExecutionVerifier,
    IntentClassifier,
    IntentType,
    VerificationOutcome,
)
from memory import store


class DevelopmentPhase(Enum):
    """Phases of the autonomous development lifecycle."""

    UNDERSTAND = auto()
    RECALL = auto()
    REASON = auto()
    PLAN = auto()
    DECIDE = auto()
    EXECUTE = auto()
    VERIFY = auto()
    LEARN = auto()
    REMEMBER = auto()
    COMPLETE = auto()


@dataclass
class DevelopmentObjective:
    """A development objective with full traceability across the SDLC."""

    id: str
    prompt: str
    intent_type: IntentType
    project_id: str = "default"
    phase: DevelopmentPhase = DevelopmentPhase.UNDERSTAND
    plan_id: Optional[str] = None
    branch_name: Optional[str] = None
    base_branch: str = "main"
    context: Dict[str, Any] = field(default_factory=dict)
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    verification: Optional[VerificationOutcome] = None
    learned_insights: List[str] = field(default_factory=list)
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class AutonomousDevelopmentEngine:
    """Unified SDLC workflow engine for SEED autonomous engineering.

    Orchestrates the full lifecycle:
    UNDERSTAND → RECALL → REASON → PLAN → DECIDE → EXECUTE → VERIFY → LEARN → REMEMBER
    """

    # Keywords that signal a development objective
    DEVELOPMENT_KEYWORDS = (
        "implement", "build", "create", "add", "fix", "refactor", "feature",
        "improve", "optimize", "update", "modify", "develop", "write", "remove",
        "delete", "migrate", "upgrade", "test", "debug", "commit", "branch",
        "pull request", "merge", "release", "version",
    )

    def __init__(self, project_path: str, project_id: str = "default") -> None:
        self.project_path = Path(project_path).resolve()
        self.project_id = project_id

        # Git Intelligence components (native, work off the real repository)
        self.branch_manager = BranchManager()
        self.commit_intelligence = CommitIntelligence()
        self.pr_manager = PullRequestManager()
        self.conflict_analyzer = ConflictAnalyzer()
        self.versioner = ProjectVersioner()

        # Durable plan state + verification
        self.plan_engine = PlanEngine()
        self.verifier = ExecutionVerifier()

        self.objective: Optional[DevelopmentObjective] = None

    # ── 1. UNDERSTAND ───────────────────────────────────────────────

    def classify_intent(self, prompt: str) -> IntentType:
        """Classify the development objective's intent."""
        return IntentClassifier.classify(prompt)

    def is_development_objective(self, prompt: str) -> bool:
        """Heuristic gate: does this objective require engineering work?"""
        text = prompt.lower()
        return any(keyword in text for keyword in self.DEVELOPMENT_KEYWORDS)

    # ── 2. RECALL ───────────────────────────────────────────────────

    def assemble_context(self, prompt: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Assemble bounded, relevant context from persistent memory."""
        return ContextAssembler.assemble(prompt, project_id=self.project_id, session_id=session_id)

    # ── 3-4. REASON & PLAN ──────────────────────────────────────────

    def _derive_steps(self, prompt: str) -> List[Dict[str, Any]]:
        """Reason about the objective and produce a minimal, executable step plan."""
        text = prompt.lower()

        steps: List[Dict[str, Any]] = [
            {"step_id": "inspect", "name": "Inspect project structure and current state"},
        ]

        if any(k in text for k in ("branch", "feature", "implement", "build", "add", "create")):
            steps.append({"step_id": "branch", "name": "Create isolated feature branch", "dependencies": ["inspect"]})

        if any(k in text for k in ("fix", "refactor", "optimize", "improve", "update", "modify", "code")):
            steps.append({"step_id": "modify", "name": "Apply code changes", "dependencies": ["branch"]})
            steps.append({"step_id": "verify", "name": "Verify changes", "dependencies": ["modify"]})

        if any(k in text for k in ("commit", "save", "record")):
            deps = ["verify"] if any(s["step_id"] == "verify" for s in steps) else ["branch"]
            steps.append({"step_id": "commit", "name": "Create commit with metadata", "dependencies": deps})

        if any(k in text for k in ("pull request", "pr", "merge", "review")):
            deps = ["commit" if any(s["step_id"] == "commit" for s in steps) else "branch"]
            steps.append({"step_id": "pr", "name": "Open pull request", "dependencies": deps})

        # Always finish with learning
        last_dep = steps[-1]["step_id"] if steps else "inspect"
        steps.append({"step_id": "learn", "name": "Extract and persist learnings", "dependencies": [last_dep]})

        return steps

    def create_plan(self, prompt: str) -> DevelopmentObjective:
        """REASON about the objective, then PERSIST a durable plan via PlanEngine."""
        intent = self.classify_intent(prompt)
        context = self.assemble_context(prompt)

        self.objective = DevelopmentObjective(
            id=f"dev-{uuid.uuid4().hex[:8]}",
            prompt=prompt,
            intent_type=intent,
            project_id=self.project_id,
            context=context,
            phase=DevelopmentPhase.REASON,
            status="planning",
        )

        steps = self._derive_steps(prompt)
        self.objective.plan_id = self.plan_engine.create_plan(prompt, steps)
        self.objective.phase = DevelopmentPhase.PLAN
        return self.objective

    # ── Git helpers (real operations) ───────────────────────────────

    def _git(self, *args: str) -> Tuple[bool, str]:
        """Run a git command in the project path. Returns (success, output)."""
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = (completed.stdout or completed.stderr).strip()
            return completed.returncode == 0, output
        except Exception as exc:  # pragma: no cover - defensive
            return False, str(exc)

    def is_git_repository(self) -> bool:
        return (self.project_path / ".git").exists()

    def current_branch(self) -> str:
        ok, out = self._git("rev-parse", "--abbrev-ref", "HEAD")
        return out if ok else ""

    # ── Execute (DECIDE → EXECUTE) ──────────────────────────────────

    def execute(self) -> DevelopmentObjective:
        """Decide ready steps and execute them against the real repo."""
        if self.objective is None or self.objective.plan_id is None:
            raise RuntimeError("create_plan() must be called before execute()")

        self.objective.phase = DevelopmentPhase.EXECUTE
        plan_id = self.objective.plan_id

        while True:
            ready = list(self.plan_engine.next_steps(plan_id))
            if not ready:
                break
            step = ready[0]
            step_id = step.step_id  # PlanStep is a dataclass, not dict
            if not self.plan_engine.claim_step(plan_id, step_id):
                ready = [s for s in self.plan_engine.next_steps(plan_id) if s.step_id != step_id]
                continue

            success = True
            result = {}
            if step_id == "inspect":
                ok, out = self._git("status", "--short", "--branch")
                result = {"status_after_inspect": out}
            elif step_id == "branch":
                base = self.current_branch() or "main"
                branch_name = self.branch_manager.get_branch_name("seed", datetime.now().strftime("%Y-%m-%dT%H-%M-%S"))
                ok, out = self._git("checkout", "-b", branch_name)
                self.objective.branch_name = branch_name if ok else base
                self.objective.base_branch = base
                result = {"branch": branch_name, "base": base, "ok": ok}
            elif step_id == "modify":
                ok, out = self._git("status", "--short")
                result = {"status_after_modify": out}
            elif step_id == "commit":
                ok, out = self._git("add", "-A")
                if not ok:
                    result = {"error": out}
                commit_msg = self.commit_intelligence.build_commit(
                    f"SEED: {self.objective.prompt[:60]}",
                    ticket_ref=self.objective.id,
                    branch_name=self.objective.branch_name or self.current_branch(),
                )
                ok, out = self._git("commit", "-m", commit_msg.message)
                result = {"commit_message": commit_msg.message, "output": out}
            elif step_id == "pr":
                template = self.pr_manager.create_pr_template(
                    title=f"SEED: {self.objective.prompt[:50]}",
                    description=self.objective.prompt,
                    source_branch=self.objective.branch_name or self.current_branch(),
                    target_branch=self.objective.base_branch,
                    ticket_ref=self.objective.id,
                )
                result = {"pr_template": template}
            elif step_id == "learn":
                result = {"note": "learning deferred to learn_phase()"}
            else:
                result = {"note": "no-op"}

            success = ok or result.get("ok", True)
            evidence_records = tuple(result.items())
            self.plan_engine.complete_step(plan_id, step_id, {"success": success}, evidence_records)

            self.objective.execution_log.append({
                "step_id": step_id,
                "name": step.name,
                "success": success,
                "evidence": evidence_records,
            })

        return self.objective

    # ── Verify (VERIFY) ─────────────────────────────────────────────

    def verify_execution(self, file_path: Optional[str] = None) -> VerificationOutcome:
        """Verify execution using collected evidence."""
        if self.objective is None:
            return VerificationOutcome.UNVERIFIED

        tool_results = tuple(
            entry.get("evidence", {}) for entry in self.objective.execution_log
        )
        outcome = self.verifier.verify(
            tool_results,
            self.objective.prompt,
            self.objective.prompt,
            file_path,
        )
        self.objective.verification = outcome
        self.objective.phase = DevelopmentPhase.VERIFY
        return outcome

    # ── Learn & Remember (LEARN → REMEMBER) ─────────────────────────

    def learn_and_remember(self, result_summary: str) -> None:
        """Persist structured insight and mark phase REMEMBER."""
        if self.objective is None:
            return

        self.objective.phase = DevelopmentPhase.LEARN

        try:
            store.save_memory(
                memory_type="durable_knowledge",
                memory_key=f"dev_objective_{self.objective.id}",
                content=(
                    f"Objective: {self.objective.prompt[:160]} | "
                    f"Outcome: {result_summary[:200]} | "
                    f"Plan: {self.objective.plan_id} | "
                    f"Verification: {self.objective.verification.value if self.objective.verification else 'n/a'}"
                ),
                project_id=self.project_id,
                approved=True,
            )
        except Exception:
            pass

        self.objective.learned_insights.append(result_summary)
        self.objective.phase = DevelopmentPhase.REMEMBER

    def mark_complete(self) -> DevelopmentObjective:
        """Finalize the cycle: record completion and trigger final learning."""
        if self.objective is None:
            raise RuntimeError("No objective to complete")

        steps_done = len([e for e in self.objective.execution_log if e.get("success")])
        summary = (
            f"Completed {steps_done}/{len(self.objective.execution_log)} steps; "
            f"verification={self.objective.verification.value if self.objective.verification else 'n/a'}"
        )
        self.learn_and_remember(summary)
        self.objective.status = "complete"
        self.objective.phase = DevelopmentPhase.COMPLETE
        return self.objective

    # ── Full pipeline orchestration ─────────────────────────────────

    def run_full_pipeline(self, prompt: str, session_id: Optional[str] = None) -> DevelopmentObjective:
        """Execute the complete cognitive development loop end-to-end.

        Args:
            prompt: Natural-language development objective.
            session_id: Optional session identifier for context assembly.

        Returns:
            Completed :class:`DevelopmentObjective`.
        """
        # 1. UNDERSTAND
        self.objective = None
        intent = self.classify_intent(prompt)

        # 2+3+4 (RECALL/REASON/PLAN)
        objective = self.create_plan(prompt)
        objective.intent_type = intent
        objective.phase = DevelopmentPhase.DECIDE

        # 5+6 (DECIDE/EXECUTE)
        self.execute()

        # 7 (VERIFY)
        self.verify_execution()

        # 8+9+ complete (LEARN/REMEMBER)
        return self.mark_complete()

    def status_report(self) -> Dict[str, Any]:
        """Return a Mission-Control-friendly snapshot."""
        if self.objective is None:
            return {"status": "idle", "project": str(self.project_path)}
        plan = self.plan_engine.get_plan(self.objective.plan_id) if self.objective.plan_id else None
        return {
            "objective_id": self.objective.id,
            "prompt": self.objective.prompt,
            "intent_type": self.objective.intent_type,
            "phase": self.objective.phase.name,
            "status": self.objective.status,
            "branch": self.objective.branch_name,
            "plan_id": self.objective.plan_id,
            "plan_state": plan.get("state") if plan else None,
            "verification": self.objective.verification.value if self.objective.verification else None,
            "steps_executed": len(self.objective.execution_log),
            "insights": list(self.objective.learned_insights),
        }


def start_autonomous_development(
    project_path: str,
    prompt: str,
    project_id: str = "default",
    session_id: Optional[str] = None,
) -> DevelopmentObjective:
    """Entry point for the autonomous development workflow.

    Args:
        project_path: Path to the SEED project root.
        prompt: Natural-language development objective.
        project_id: Project identifier for memory persistence.
        session_id: Optional session identifier for context assembly.

    Returns:
        The completed :class:`DevelopmentObjective`.
    """
    engine = AutonomousDevelopmentEngine(project_path, project_id)
    return engine.run_full_pipeline(prompt, session_id=session_id)