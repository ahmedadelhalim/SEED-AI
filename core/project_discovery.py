"""
Project Discovery Module for SEED Autonomous Software Engineering System

Discovers repositories, understands architecture, dependencies, branches,
history, and development state. Native capability integrated with CognitiveEngine
and AutonomousAgent.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json

from core.git_intelligence import BranchManager


@dataclass
class ProjectStructure:
    """Represents discovered project architecture."""
    name: str
    root_path: Path
    language: str = ""
    framework: str = ""
    build_system: str = ""
    entry_points: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    branches: List[str] = field(default_factory=list)
    active_branch: str = ""
    git_state: str = "unknown"
    test_directories: List[str] = field(default_factory=list)
    source_directories: List[str] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    last_commit_hash: str = ""
    last_commit_message: str = ""
    repository_size: int = 0


@dataclass
class DependencyAnalysis:
    """Represents project dependency landscape."""
    direct: List[str] = field(default_factory=list)
    transitive: List[str] = field(default_factory=list)
    outdated: List[str] = field(default_factory=list)
    vulnerabilities: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)


@dataclass
class DiscoveryResult:
    """Complete discovery result for a project."""
    project_structure: ProjectStructure
    dependency_analysis: DependencyAnalysis
    git_intelligence: Dict[str, Any]
    recommendations: List[str] = field(default_factory=list)


class ProjectDiscovery:
    """
    Native Project Discovery capability for SEED autonomous engineering.
    
    Discovers repositories, understands their architecture, dependencies,
    branches, history, and development state. Works through CognitiveEngine
    intent classification and integrates with AutonomousAgent execution.
    """

    SUPPORTED_BUILD_SYSTEMS = {
        "pyproject.toml": "python",
        "setup.py": "python",
        "requirements.txt": "python",
        "pom.xml": "java",
        "build.gradle": "java",
        "package.json": "javascript/typescript",
        "Cargo.toml": "rust",
        "go.mod": "go",
        ".csproj": "dotnet",
    }

    def __init__(self, application=None):
        self.application = application
        self.branch_manager = BranchManager()

    def discover_project(self, project_path: str, project_id: str = "default") -> DiscoveryResult:
        """
        Discover project structure, dependencies, git state, and development context.
        
        Args:
            project_path: Path to the project root
            project_id: Project identifier for memory persistence
            
        Returns:
            DiscoveryResult with complete project analysis
        """
        path = Path(project_path).resolve()
        structure = self._discover_structure(path)
        dependencies = self._analyze_dependencies(path)
        git_state = self._discover_git_state(path)
        recommendations = self._generate_recommendations(structure, dependencies, git_state)

        result = DiscoveryResult(
            project_structure=structure,
            dependency_analysis=dependencies,
            git_intelligence=git_state,
            recommendations=recommendations,
        )

        # Store discovery in memory for continuous project memory
        self._persist_discovery(result, project_id)

        return result

    def _discover_structure(self, path: Path) -> ProjectStructure:
        """Discover project files, language, build system, and architecture."""
        structure = ProjectStructure(
            name=path.name,
            root_path=path,
        )

        # Detect language and build system
        for config_file in sorted(self.SUPPORTED_BUILD_SYSTEMS.keys()):
            config_path = path / config_file
            if config_path.exists():
                structure.language = self.SUPPORTED_BUILD_SYSTEMS[config_file]
                structure.build_system = config_file
                structure.config_files.append(str(config_path))
                break

        # Discover directories
        for entry in path.iterdir():
            if entry.is_dir() and entry.name not in (".git", "__pycache__", ".venv", "node_modules"):
                if entry.name.lower() in ("src", "lib", "source", "app"):
                    structure.source_directories.append(str(entry))
                elif entry.name.lower() in ("test", "tests", "spec", "__tests__"):
                    structure.test_directories.append(str(entry))
                else:
                    structure.source_directories.append(str(entry))

        # Discover source files for language hints
        if structure.language == "python":
            py_files = list(path.rglob("*.py"))[:50]
            structure.entry_points.extend([str(f.relative_to(path)) for f in py_files if f.name == "main.py"])

        return structure

    def _analyze_dependencies(self, path: Path) -> DependencyAnalysis:
        """Analyze project dependencies."""
        analysis = DependencyAnalysis()

        requirements_path = path / "requirements.txt"
        if requirements_path.exists():
            try:
                with open(requirements_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                analysis.direct = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
            except Exception:
                pass

        pyproject_path = path / "pyproject.toml"
        if pyproject_path.exists():
            try:
                with open(pyproject_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Simple extraction for dependencies section
                if "[tool.poetry.dependencies]" in content:
                    analysis.direct.append("poetry-managed")
            except Exception:
                pass

        return analysis

    def _discover_git_state(self, path: Path) -> Dict[str, Any]:
        """Discover git branches, history, and repository state."""
        try:
            branches = self.branch_manager.list_branches(str(path))
            active = ""
            for branch in branches:
                if isinstance(branch, dict) and branch.get("active"):
                    active = branch.get("name", "")
                    break
            elif isinstance(branches, list):
                active = branches[0].get("name", "") if branches else ""

            return {
                "branches": branches,
                "active_branch": active,
                "repository": str(path),
                "is_git_repo": (path / ".git").exists(),
            }
        except Exception as e:
            return {
                "branches": [],
                "active_branch": "",
                "repository": str(path),
                "is_git_repo": (path / ".git").exists(),
                "error": str(e),
            }

    def _generate_recommendations(
        self,
        structure: ProjectStructure,
        dependencies: DependencyAnalysis,
        git_state: Dict[str, Any],
    ) -> List[str]:
        """Generate recommendations for autonomous development."""
        recommendations = []

        if not structure.source_directories:
            recommendations.append("No source directories detected - project may be minimal")

        if not structure.test_directories:
            recommendations.append("No test directories found - consider adding test suite")

        if not git_state.get("is_git_repo"):
            recommendations.append("Not a git repository - initialize for version control")

        if structure.build_system == "":
            recommendations.append("No recognized build system - consider adding configuration")

        if not dependencies.direct:
            recommendations.append("No direct dependencies detected - minimal project")

        recommendations.append(f"Detected {structure.language} project - ready for autonomous development")

        return recommendations

    def _persist_discovery(self, result: DiscoveryResult, project_id: str) -> None:
        """Store discovery results in memory for continuous project memory."""
        try:
            content = json.dumps({
                "project_name": result.project_structure.name,
                "language": result.project_structure.language,
                "build_system": result.project_structure.build_system,
                "active_branch": result.git_intelligence.get("active_branch", ""),
                "recommendations": result.recommendations,
            })
            store.save_memory(
                memory_type="project_discovery",
                memory_key=f"discovery_{project_id}",
                content=content,
                project_id=project_id,
                approved=True,
            )
        except Exception:
            pass


__all__ = [
    "ProjectDiscovery",
    "ProjectStructure",
    "DependencyAnalysis",
    "DiscoveryResult",
]
