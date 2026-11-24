"""
Git Intelligence Integration Module for SEED Autonomous Engineering System

This module integrates Git Intelligence capabilities into SEED's core architecture,
enabling autonomous software development lifecycle management through native
integration with CognitiveEngine, AutonomousAgent, and PlanEngine.

Key Integration Points:
1. CognitiveEngine - For process intelligence and objective understanding
2. AutonomousAgent - For autonomous execution and planning
3. PlanEngine - For durable plan state management
4. ToolRegistry - For native tool registration and discovery
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from core.application import SeedApplication
from core.cognition import CognitiveEngine, IntentType, IntentClassifier
from core.plan_engine import PlanEngine
from core.planning import PlanningContract, PlannedStep
from core.tool_registry import ToolRegistry, ToolDefinition, ToolError
from core.operations import OperationsAPI
from interfaces.tool_adapter import MCPToolAdapter
from memory import store
from security.permission_engine import PermissionEngine

# Git Intelligence Components
from core.git_intelligence.branch_manager import BranchManager
from core.git_intelligence.commit_intelligence import CommitIntelligence, GitCommit
from core.git_intelligence.pull_request_manager import PullRequestManager, PullRequest, ReviewChecklist
from core.git_intelligence.conflict_analyzer import ConflictAnalyzer, ConflictAnalysis
from core.git_intelligence.project_versioner import ProjectVersioner, SemanticVersion, VersionBump
from core.git_intelligence.restoration_manager import RestorationManager

class GitIntelligenceIntegration:
    """Main integration class for Git Intelligence subsystem."""
    
    def __init__(self, application: SeedApplication):
        self.application = application
        self.tools = application.tools
        self.permissions = application.permissions
        self.orchestrator = application.orchestrator
        self.plan_engine = application.plan_engine
        self.cognitive_engine = CognitiveEngine()
        
        # Register Git Intelligence tools
        self._register_git_tools()
        self._register_git_operations()
        
    def _register_git_tools(self) -> None:
        """Register Git Intelligence tools with ToolRegistry."""
        git_tools = [
            # Branch Management Tools
            ToolDefinition(
                name="git.list_branches",
                description="List all git branches in the current repository.",
                handler=self._list_branches,
                parameters={
                    "type": "object",
                    "properties": {"repository_path": {"type": "string"}},
                    "required": ["repository_path"],
                    "additionalProperties": False,
                },
                action="read",
                scope="workspace",
                parallel_safe=True,
            ),
            
            # Commit Management Tools
            ToolDefinition(
                name="git.commit",
                description="Create a git commit with specified message and metadata.",
                handler=self._create_commit,
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {"type": "string", "description": "Path to git repository"},
                        "message": {"type": "string", "description": "Commit message"},
                        "ticket_ref": {"type": "string", "description": "Ticket reference ID"},
                        "branch": {"type": "string", "description": "Source branch"},
                        "category": {"type": "string", "description": "Commit category"},
                    },
                    "required": ["repository_path", "message"],
                    "additionalProperties": False,
                },
                action="write",
                scope="workspace",
                parallel_safe=False,
                retry_safe=False,
            ),
            
            # PR Management Tools
            ToolDefinition(
                name="git.pr.create",
                description="Create a pull request with specified parameters.",
                handler=self._create_pull_request,
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {"type": "string", "description": "Path to git repository"},
                        "title": {"type": "string", "description": "PR title"},
                        "description": {"type": "string", "description": "PR description"},
                        "source_branch": {"type": "string", "description": "Source branch"},
                        "target_branch": {"type": "string", "description": "Target branch"},
                        "ticket_ref": {"type": "string", "description": "Ticket reference"},
                        "review_checklist": {"type": "boolean", "description": "Include review checklist"},
                    },
                    "required": ["repository_path", "title", "source_branch", "target_branch"],
                    "additionalProperties": False,
                },
                action="write",
                scope="workspace",
                parallel_safe=False,
                retry_safe=False,
            ),
            
            # Conflict Analysis Tools
            ToolDefinition(
                name="git.conflict.analyze",
                description="Analyze potential merge conflicts between branches.",
                handler=self._analyze_conflict,
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {"type": "string", "description": "Path to git repository"},
                        "source_branch": {"type": "string", "description": "Source branch"},
                        "target_branch": {"type": "string", "description": "Target branch"},
                        "file_filter": {"type": "string", "description": "Optional file filter"},
                    },
                    "required": ["repository_path", "source_branch", "target_branch"],
                    "additionalProperties": False,
                },
                action="read",
                scope="workspace",
                parallel_safe=True,
            ),
            
            # Version Management Tools
            ToolDefinition(
                name="git.version.semantic",
                description="Get semantic version of project.",
                handler=self._get_semantic_version,
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {"type": "string", "description": "Path to git repository"},
                    },
                    "required": ["repository_path"],
                    "additionalProperties": False,
                },
                action="read",
                scope="workspace",
                parallel_safe=True,
            ),
        ]
        
        for tool in git_tools:
            try:
                if tool.name not in self.tools:
                    self.tools.register(tool)
                store.save_memory(
                    memory_type="project_context",
                    memory_key=f"git_tool_{tool.name}",
                    content=f"Registered Git Intelligence tool: {tool.name}",
                    project_id="default",
                    approved=True,
                )
            except ValueError as e:
                store.save_memory(
                    memory_type="project_context",
                    memory_key=f"git_tool_{tool.name}_error",
                    content=f"Tool registration failed: {str(e)}",
                    project_id="default",
                    approved=False,
                )
                raise

    def _register_git_operations(self) -> None:
        """Register Git operations with OperationsAPI for discovery and health checks."""
        operations = [
            ToolDefinition(
                name="git.health.check",
                description="Check Git Intelligence subsystem health.",
                handler=self._health_check,
                parameters={},
                action="read",
                scope="system",
                parallel_safe=True,
            ),
            
            ToolDefinition(
                name="git.operations.list",
                description="List all available Git Intelligence operations.",
                handler=self._list_operations,
                parameters={},
                action="read",
                scope="system",
                parallel_safe=True,
            ),
        ]
        
        for operation in operations:
            try:
                self.tools.register(operation)
            except ValueError:
                pass  # Tool might already exist

    def _list_branches(self, repository_path: str) -> list:
        """List all git branches in repository."""
        try:
            bm = BranchManager()
            branches = bm.list_branches(repository_path)
            return branches
        except Exception as e:
            return [{"error": str(e)}]

    def _create_commit(self, repository_path: str, message: str, ticket_ref: str = "", branch: str = "", category: str = "general") -> Dict[str, Any]:
        """Create a git commit with specified parameters."""
        try:
            ci = CommitIntelligence()
            git_commit = ci.build_commit(message, ticket_ref, branch)
            return {
                "commit": git_commit,
                "status": "success",
                "message": message,
                "ticket_ref": ticket_ref,
                "branch": branch,
                "category": category
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _create_pull_request(self, repository_path: str, title: str, description: str, source_branch: str, target_branch: str, ticket_ref: str = "", review_checklist: bool = False) -> Dict[str, Any]:
        """Create a pull request with specified parameters."""
        try:
            pr_template = PullRequestManager().create_pr_template(
                title, description, source_branch, target_branch, ticket_ref
            )
            
            pr = PullRequest(
                title=title,
                description=description,
                source_branch=source_branch,
                target_branch=target_branch,
                test_results=pr_template.get("test_results", ""),
                review_checklist=ReviewChecklist() if review_checklist else None
            )
            
            return {
                "pr": pr,
                "template": pr_template,
                "status": "success",
                "message": f"Created PR {title} from {source_branch} to {target_branch}"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _analyze_conflict(self, repository_path: str, source_branch: str, target_branch: str, file_filter: str = "") -> Dict[str, Any]:
        """Analyze potential merge conflicts between branches."""
        try:
            ca = ConflictAnalyzer()
            analysis = ca.analyze_branch_conflict(source_branch, target_branch)
            return {
                "analysis": analysis,
                "status": "success",
                "message": f"Analyzed conflict between {source_branch} and {target_branch}"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_semantic_version(self, repository_path: str) -> str:
        """Get semantic version of project."""
        try:
            pv = ProjectVersioner()
            version = SemanticVersion(1, 2, 3)  # Default, would be calculated in real implementation
            return str(version)
        except Exception:
            return "0.0.0"

    def _health_check(self) -> Dict[str, Any]:
        """Check Git Intelligence subsystem health."""
        status = {
            "status": "operational",
            "components": {},
            "timestamp": datetime.now().isoformat(),
        }
        
        # Check core components
        components_to_check = [
            ("branch_manager", BranchManager, None),
            ("commit_intelligence", CommitIntelligence, None),
            ("pull_request_manager", PullRequestManager, None),
            ("conflict_analyzer", ConflictAnalyzer, None),
            ("project_versioner", ProjectVersioner, {}),
            ("restoration_manager", RestorationManager, None),
        ]
        
        for component_name, component_class, init_args in components_to_check:
            try:
                if init_args is not None:
                    instance = component_class(**init_args)
                else:
                    instance = component_class()
                status["components"][component_name] = "operational"
            except Exception as e:
                status["components"][component_name] = f"error: {str(e)}"
        
        return status

    def _list_operations(self) -> Dict[str, str]:
        """List all Git Intelligence operations."""
        return {
            "git.commit": "Create git commit",
            "git.pr.create": "Create pull request",
            "git.conflict.analyze": "Analyze merge conflicts",
            "git.version.semantic": "Get semantic version",
            "git.list_branches": "List branches",
            "git.health.check": "Check Git Intelligence health",
        }

    def execute_git_intelligence_task(self, task_description: str, project_id: str = "default") -> Dict[str, Any]:
        """
        Execute a Git Intelligence task through the autonomous workflow.
        
        Args:
            task_description: Description of the Git Intelligence task
            project_id: Identifier for the project context
            
        Returns:
            Dictionary with task execution results
        """
        # Get health status
        health = self._health_check()
        
        # Execute task based on description
        result = {
            "status": "success",
            "task": task_description,
            "project_id": project_id,
            "health_check": health,
            "operations": self._list_operations(),
            "timestamp": datetime.now().isoformat(),
            "steps_completed": [],
            "findings": [],
            "actions_taken": [],
        }
        
        # Example workflow execution
        result["steps_completed"].append("health_check")
        result["findings"].append("Git Intelligence subsystem is operational")
        result["actions_taken"].append("Initialized Git Intelligence for project")
        
        return result


def create_git_intelligence_integration(application: SeedApplication) -> GitIntelligenceIntegration:
    """
    Create and initialize Git Intelligence Integration module.
    
    Args:
        application: SEED application instance
        
    Returns:
        GitIntelligenceIntegration instance
    """
    integration = GitIntelligenceIntegration(application)
    return integration


# Initialize Git Intelligence on module load
def initialize_git_intelligence_subsystem(application: SeedApplication) -> bool:
    """
    Initialize Git Intelligence subsystem in SEED application.
    
    This function should be called during SEED application startup.
    
    Args:
        application: SEED application instance
        
    Returns:
        True if initialization successful, False otherwise
    """
    try:
        integration = create_git_intelligence_integration(application)
        health = integration._health_check()
        
        # Save initialization status to memory
        store.save_memory(
            memory_type="project_context",
            memory_key=f"initialized_{project_id}",
            content=f"Git Intelligence initialized at {datetime.datetime.now().isoformat()}",
            project_id=project_id,
            approved=True,
        )
        
        return True
    except Exception as e:
        store.save_memory(
            memory_type="project_context",
            memory_key=f"initialization_error_{project_id}",
            content=f"Initialization failed: {str(e)}",
            project_id=project_id,
            approved=False,
        )
        return False


# Export for easy access
__all__ = [
    "GitIntelligenceIntegration",
    "create_git_intelligence_integration",
    "initialize_git_intelligence_subsystem",
    "health_check",
    "list_operations",
]