"""
Intelligent Validation System for SEED-AI.

Provides autonomous test selection, execution, failure analysis, root cause diagnosis,
and iterative improvement for continuous validation of the codebase.
"""

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.cognition import ExecutionVerifier, VerificationOutcome
from core.unified_intelligence import UnifiedIntelligenceEngine
from memory import store


class TestSelectionStrategy(str, Enum):
    CHANGED_FILES = "changed_files"           # Tests related to recently modified files
    FAILING_FIRST = "failing_first"           # Prioritize previously failing tests
    COVERAGE_GAPS = "coverage_gaps"           # Tests covering uncovered code
    FULL_SUITE = "full_suite"                 # Run entire test suite
    SMART = "smart"                           # Adaptive selection based on context


class ValidationPhase(str, Enum):
    SELECTION = "selection"
    EXECUTION = "execution"
    ANALYSIS = "analysis"
    IMPROVEMENT = "improvement"
    VERIFICATION = "verification"


@dataclass
class TestResult:
    name: str
    path: str
    status: str  # passed, failed, error, skipped
    duration_ms: float
    output: str = ""
    error_trace: str = ""
    file_path: Optional[str] = None


@dataclass
class ValidationSession:
    session_id: str
    strategy: TestSelectionStrategy
    phase: ValidationPhase = ValidationPhase.SELECTION
    selected_tests: List[str] = field(default_factory=list)
    results: List[TestResult] = field(default_factory=list)
    failure_analysis: Optional[Dict[str, Any]] = None
    improvements_applied: List[str] = field(default_factory=list)
    iterations: int = 0
    max_iterations: int = 3
    start_time: float = field(default_factory=time.time)


class TestSelector:
    """Intelligent test selection based on code changes and context."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.tests_dir = project_root / "tests"

    def select_tests(self, strategy: TestSelectionStrategy, changed_files: Optional[List[str]] = None) -> List[str]:
        all_tests = self._discover_all_tests()

        if strategy == TestSelectionStrategy.FULL_SUITE:
            return all_tests

        if strategy == TestSelectionStrategy.CHANGED_FILES and changed_files:
            return self._select_by_changed_files(all_tests, changed_files)

        if strategy == TestSelectionStrategy.FAILING_FIRST:
            return self._select_failing_first(all_tests)

        if strategy == TestSelectionStrategy.SMART:
            return self._smart_select(all_tests, changed_files)

        return all_tests

    def _discover_all_tests(self) -> List[str]:
        tests = []
        if self.tests_dir.exists():
            for test_file in self.tests_dir.glob("test_*.py"):
                tests.append(str(test_file.relative_to(self.project_root)))
        return sorted(tests)

    def _select_by_changed_files(self, all_tests: List[str], changed_files: List[str]) -> List[str]:
        # Simple heuristic: match test files by module name
        changed_modules = set()
        for f in changed_files:
            path = Path(f)
            if path.suffix == ".py":
                module = path.stem.replace("test_", "")
                changed_modules.add(module)

        selected = []
        for test in all_tests:
            test_path = Path(test)
            for mod in changed_modules:
                if mod in test_path.stem or mod in str(test_path):
                    selected.append(test)
                    break

        # Add failing tests from memory
        failing_from_memory = self._get_previously_failing_tests()
        for f in failing_from_memory:
            if f not in selected:
                selected.append(f)

        return selected or all_tests[:10]  # Fallback to first 10

    def _select_failing_first(self, all_tests: List[str]) -> List[str]:
        failing = self._get_previously_failing_tests()
        selected = [f for f in failing if f in all_tests]
        # Add remaining tests
        for test in all_tests:
            if test not in selected:
                selected.append(test)
        return selected

    def _smart_select(self, all_tests: List[str], changed_files: Optional[List[str]] = None) -> List[str]:
        # Combine strategies: changed files + previously failing + coverage gaps
        selected = set()

        if changed_files:
            for test in self._select_by_changed_files(all_tests, changed_files):
                selected.add(test)

        for test in self._select_failing_first(all_tests):
            selected.add(test)

        # Add critical path tests
        critical = [t for t in all_tests if any(kw in t.lower() for kw in ("cognition", "orchestrator", "git", "integration"))]
        for test in critical:
            selected.add(test)

        result = list(selected)
        return result if result else all_tests[:15]

    def _get_previously_failing_tests(self) -> List[str]:
        # Query memory for previously failing tests
        try:
            memories = list(store.search_memory("test_failure", project_id="default", limit=10))
            failing = []
            for mem in memories:
                content = mem.get("content", "")
                if ".py" in content:
                    for line in content.split("\n"):
                        if "test_" in line and ".py" in line:
                            failing.append(line.strip())
            return failing
        except Exception:
            return []


class TestExecutor:
    """Executes tests and captures structured results."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_tests(self, test_paths: List[str], timeout: int = 120) -> List[TestResult]:
        results = []

        for test_path in test_paths:
            start = time.time()
            full_path = self.project_root / test_path

            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pytest", str(full_path), "-v", "--tb=short"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                duration_ms = (time.time() - start) * 1000

                status = "passed"
                if proc.returncode != 0:
                    status = "failed" if "FAILED" in proc.stdout else "error"

                results.append(TestResult(
                    name=Path(test_path).stem,
                    path=test_path,
                    status=status,
                    duration_ms=duration_ms,
                    output=proc.stdout,
                    error_trace=proc.stderr,
                    file_path=test_path,
                ))

            except subprocess.TimeoutExpired:
                results.append(TestResult(
                    name=Path(test_path).stem,
                    path=test_path,
                    status="timeout",
                    duration_ms=timeout * 1000,
                    error_trace=f"Test timed out after {timeout}s",
                ))
            except Exception as e:
                results.append(TestResult(
                    name=Path(test_path).stem,
                    path=test_path,
                    status="error",
                    duration_ms=(time.time() - start) * 1000,
                    error_trace=str(e),
                ))

        return results


class FailureAnalyzer:
    """Analyzes test failures for root cause and suggests fixes."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def analyze_failures(self, results: List[TestResult]) -> Dict[str, Any]:
        failed = [r for r in results if r.status in ("failed", "error", "timeout")]

        if not failed:
            return {"has_failures": False, "root_causes": [], "suggestions": []}

        root_causes = []
        suggestions = []

        for result in failed:
            trace = result.error_trace or result.output
            causes = self._extract_root_causes(trace)
            root_causes.extend(causes)

            sug = self._suggest_fixes(result.name, trace, result.file_path)
            suggestions.extend(sug)

        # Deduplicate
        root_causes = list(dict.fromkeys(root_causes))
        suggestions = list(dict.fromkeys(suggestions))

        # Store failure patterns in memory
        self._store_failure_pattern(failed)

        return {
            "has_failures": True,
            "failed_count": len(failed),
            "root_causes": root_causes,
            "suggestions": suggestions,
            "failed_tests": [r.name for r in failed],
        }

    def _extract_root_causes(self, trace: str) -> List[str]:
        causes = []

        # Common Python failure patterns
        patterns = [
            ("ImportError", "Missing import or module"),
            ("ModuleNotFoundError", "Module not installed"),
            ("AttributeError", "Missing attribute/method"),
            ("TypeError", "Type mismatch in function call"),
            ("AssertionError", "Test assertion failed"),
            ("FileNotFoundError", "Missing file or resource"),
            ("ConnectionError", "Network/service unavailable"),
            ("TimeoutError", "Operation timed out"),
        ]

        for pattern, cause in patterns:
            if pattern in trace:
                causes.append(f"{pattern}: {cause}")

        # Extract specific error lines
        for line in trace.split("\n"):
            line = line.strip()
            if "Error:" in line or "Exception:" in line or "FAILED" in line:
                if len(line) < 200:
                    causes.append(line)

        return causes[:10]

    def _suggest_fixes(self, test_name: str, trace: str, file_path: Optional[str]) -> List[str]:
        suggestions = []

        if "ModuleNotFoundError" in trace:
            suggestions.append("Install missing dependencies: pip install -r requirements.txt")
        if "ImportError" in trace:
            suggestions.append("Fix import paths or install missing packages")
        if "AssertionError" in trace:
            suggestions.append(f"Review test assertions in {test_name} - expected vs actual mismatch")
        if "AttributeError" in trace:
            suggestions.append(f"Check {test_name} for API changes - method/attribute may have been renamed")
        if "ConnectionError" in trace or "ProviderError" in trace:
            suggestions.append("Verify external service connectivity (Ollama, database, etc.)")
        if "FileNotFoundError" in trace:
            suggestions.append(f"Check file paths in {test_name} - resources may have moved")

        if file_path:
            suggestions.append(f"Examine {file_path} for recent changes that could cause failures")

        return suggestions

    def _store_failure_pattern(self, failed_results: List[TestResult]):
        try:
            for result in failed_results:
                key = f"test_failure:{result.name}"
                content = f"Test: {result.name}\nFile: {result.file_path}\nTrace:\n{result.error_trace or result.output}"
                store.save_memory(
                    memory_type="durable_knowledge",
                    memory_key=key,
                    content=content,
                    project_id="default",
                    approved=True,
                )
        except Exception:
            pass


class ImprovementEngine:
    """Applies iterative improvements to fix failing tests."""

    def __init__(self, project_root: Path, unified_intelligence: UnifiedIntelligenceEngine):
        self.project_root = project_root
        self.intelligence = unified_intelligence

    def attempt_fixes(self, analysis: Dict[str, Any], max_attempts: int = 3) -> List[str]:
        applied = []

        for suggestion in analysis.get("suggestions", []):
            if len(applied) >= max_attempts:
                break

            fix_result = self._apply_suggestion(suggestion, analysis)
            if fix_result:
                applied.append(fix_result)

        return applied

    def _apply_suggestion(self, suggestion: str, analysis: Dict[str, Any]) -> Optional[str]:
        # This is a placeholder for automated fix application.
        # In a real system, this would use LLM-guided code edits.
        # For now, we log the suggestion for manual/agentic application.
        return f"Logged for agentic fix: {suggestion[:100]}"


class IntelligentValidationSystem:
    """
    Orchestrates the full validation loop:
    SELECTION -> EXECUTION -> ANALYSIS -> IMPROVEMENT -> VERIFICATION
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        unified_intelligence: Optional[UnifiedIntelligenceEngine] = None,
        memory_store=None,
    ):
        self.project_root = project_root or Path.cwd()
        self.memory_store = memory_store or store
        self.intelligence = unified_intelligence or UnifiedIntelligenceEngine()

        self.selector = TestSelector(self.project_root)
        self.executor = TestExecutor(self.project_root)
        self.analyzer = FailureAnalyzer(self.project_root)
        self.improver = ImprovementEngine(self.project_root, self.intelligence)

    def validate(
        self,
        strategy: TestSelectionStrategy = TestSelectionStrategy.SMART,
        changed_files: Optional[List[str]] = None,
        max_iterations: int = 3,
    ) -> Dict[str, Any]:
        """
        Run the complete intelligent validation loop.
        """
        session_id = f"validation_{int(time.time())}"
        session = ValidationSession(
            session_id=session_id,
            strategy=strategy,
            max_iterations=max_iterations,
        )

        # Phase 1: Selection
        session.phase = ValidationPhase.SELECTION
        session.selected_tests = self.selector.select_tests(strategy, changed_files)

        # Phase 2: Execution
        session.phase = ValidationPhase.EXECUTION
        session.results = self.executor.run_tests(session.selected_tests)

        # Phase 3: Analysis
        session.phase = ValidationPhase.ANALYSIS
        session.failure_analysis = self.analyzer.analyze_failures(session.results)

        # Phase 4: Improvement (iterative)
        if session.failure_analysis.get("has_failures"):
            session.phase = ValidationPhase.IMPROVEMENT
            for iteration in range(max_iterations):
                session.iterations = iteration + 1
                improvements = self.improver.attempt_fixes(session.failure_analysis)
                session.improvements_applied.extend(improvements)

                if not improvements:
                    break

                # Re-run failed tests
                failed_names = session.failure_analysis.get("failed_tests", [])
                retry_tests = [t for t in session.selected_tests if Path(t).stem in failed_names]
                if retry_tests:
                    session.results = self.executor.run_tests(retry_tests)
                    session.failure_analysis = self.analyzer.analyze_failures(session.results)
                    if not session.failure_analysis.get("has_failures"):
                        break

        # Phase 5: Verification
        session.phase = ValidationPhase.VERIFICATION
        final_outcome = self._verify_session(session)

        # Store session results
        self._store_session_result(session)

        return {
            "session_id": session_id,
            "strategy": strategy.value,
            "selected_tests": len(session.selected_tests),
            "total_duration_ms": (time.time() - session.start_time) * 1000,
            "passed": sum(1 for r in session.results if r.status == "passed"),
            "failed": sum(1 for r in session.results if r.status in ("failed", "error", "timeout")),
            "iterations": session.iterations,
            "improvements_applied": session.improvements_applied,
            "final_outcome": final_outcome.value,
            "failure_analysis": session.failure_analysis,
        }

    def _verify_session(self, session: ValidationSession) -> VerificationOutcome:
        # Build execution result for ExecutionVerifier
        exec_result = {
            "tool_results": tuple(
                {"name": r.name, "status": r.status, "duration_ms": r.duration_ms}
                for r in session.results
            ),
            "response": f"Validation complete: {len(session.results)} tests executed",
            "file_path": None,
        }

        objective = f"Run validation with strategy {session.strategy.value}"
        return ExecutionVerifier.verify(exec_result, "", objective)

    def _store_session_result(self, session: ValidationSession):
        try:
            key = f"validation_session:{session.session_id}"
            content = f"Strategy: {session.strategy.value}\n" \
                      f"Tests: {len(session.selected_tests)}\n" \
                      f"Passed: {sum(1 for r in session.results if r.status == 'passed')}\n" \
                      f"Failed: {sum(1 for r in session.results if r.status in ('failed', 'error', 'timeout'))}\n" \
                      f"Iterations: {session.iterations}\n" \
                      f"Outcome: {session.failure_analysis}"
            self.memory_store.save_memory(
                memory_type="durable_knowledge",
                memory_key=key,
                content=content,
                project_id="default",
                approved=True,
            )
        except Exception:
            pass


def run_intelligent_validation(
    strategy: TestSelectionStrategy = TestSelectionStrategy.SMART,
    changed_files: Optional[List[str]] = None,
    max_iterations: int = 3,
    project_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience function to run the intelligent validation system."""
    root = Path(project_root) if project_root else Path.cwd()
    system = IntelligentValidationSystem(project_root=root)
    return system.validate(strategy, changed_files, max_iterations)