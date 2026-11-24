"""
Engineering Intelligence Module for SEED Autonomous Software Engineering System

Understands codebase requirements, identifies defects, evaluates architecture,
and provides intelligent recommendations for development.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import json

from core.git_intelligence import ProjectVersioner
from memory import store


@dataclass
class Requirement:


@dataclass
class Requirement:
    """Represents a software requirement or user story."""
    id: str
    description: str
    priority: str = "medium"
    tags: List[str] = field(default_factory=list)


@dataclass
class Defect:
    """Represents a code defect or issue."""
    id: str
    description: str
    severity: str = "low"
    type: str = "bug"
    related_requirement: Optional[str] = None


@dataclass
class ArchitectureInsight:
    """Represents architectural evaluation and recommendations."""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    architectural_patterns: List[str] = field(default_factory=list)
    tech_debt: str = ""


@dataclass
class EngineeringInsight:
    """Complete engineering intelligence analysis."""
    requirements: List[Requirement] = field(default_factory=list)
    defects: List[Defect] = field(default_factory=list)
    architecture: ArchitectureInsight = field(default_factory=lambda: ArchitectureInsight())
    recommendations: List[str] = field(default_factory=list)
    confidence_score: float = 0.0


class EngineeringIntelligence:
    """
    Native Engineering Intelligence capability for SEED autonomous engineering.
    
    Understands codebase requirements, identifies defects, evaluates architecture,
    and provides intelligent recommendations. Integrated with CognitiveEngine
    for intent classification and AutonomousAgent for execution.
    """

    def __init__(self, application=None):
        self.application = application
        self.versioner = ProjectVersioner()

    def analyze_codebase(self, project_path: str, project_id: str = "default") -> EngineeringInsight:
        """
        Analyze project codebase for requirements, defects, and architectural insights.
        
        Args:
            project_path: Path to project root
            project_id: Project identifier for memory persistence
            
        Returns:
            EngineeringInsight with complete analysis
        """
        insight = EngineeringInsight()
        
        # Discover requirements from code comments, README, etc.
        requirements = self._extract_requirements(project_path)
        insight.requirements = requirements
        
        # Identify defects and issues
        defects = self._identify_defects(project_path)
        insight.defects = defects
        
        # Evaluate architecture
        architecture = self._evaluate_architecture(project_path)
        insight.architecture = architecture
        
        # Generate recommendations
        recommendations = self._generate_recommendations(insight)
        insight.recommendations = recommendations
        
        # Set confidence based on analysis completeness
        insight.confidence_score = self._calculate_confidence(insight)
        
        # Store in memory for continuous project memory
        self._persist_insight(insight, project_id)
        
        return insight

    def _extract_requirements(self, project_path: str) -> List[Requirement]:
        """Extract software requirements from codebase artifacts."""
        requirements = []
        path = Path(project_path)
        
        # Look for requirement documentation
        req_files = ["requirements.md", "README.md", "spec.md", "user_stories.md", "feature_list.md"]
        for req_file in req_files:
            file_path = path / req_file
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Simple pattern matching for requirements
                    for line in content.split("\n"):
                        line = line.strip()
                        if line and line.startswith(("Req", "User Story", "Feature", "EPIC", "Goal")):
                            # Parse requirement ID and description
                            if ":" in line:
                                parts = line.split(":", 1)
                                req_id = parts[0].strip()
                                description = parts[1].strip()
                                requirements.append(
                                    Requirement(
                                        id=req_id,
                                        description=description,
                                        priority="high" if "CRITICAL" in description or "HIGH" in description else "medium",
                                        tags=[t.strip() for t in line.split(",") if t.strip().startswith("tag")],
                                    )
                                )
                except Exception:
                    pass
        
        return requirements

    def _identify_defects(self, project_path: str) -> List[Defect]:
        """Identify code defects and issues."""
        defects = []
        path = Path(project_path)
        
        # Look for defect indicators in comments, logs, etc.
        for py_file in path.rglob("*.py"):
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Look for TODO, FIXME, BUG comments
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if "TODO" in line or "FIXME" in line or "BUG" in line:
                        defect_id = f"defect_{py_file.name}_{i}"
                        defect_type = "enhancement" if "TODO" in line else "bug" if "BUG" in line else "technical"
                        defects.append(
                            Defect(
                                id=defect_id,
                                description=f"{defect_type.upper()}: {line.strip()}",
                                severity="high" if "BUG" in line else "medium" if "FIXME" in line else "low",
                                type=defect_type,
                            )
                        )
            except Exception:
                pass
                
        return defects

    def _evaluate_architecture(self, project_path: str) -> ArchitectureInsight:
        """Evaluate project architecture and identify patterns and tech debt."""
        path = Path(project_path)
        strengths = []
        weaknesses = []
        improvements = []
        architectural_patterns = []
        tech_debt = "low"
        
        # Simple heuristic-based analysis
        py_files = list(path.rglob("*.py"))[:100]  # Limit for performance
        if py_files:
            # Check for MVC pattern
            has_mvc = any("models" in str(p).lower() and "views" in str(p).lower() and "controllers" in str(p).lower() 
                         for p in py_files)
            if has_mvc:
                architectural_patterns.append("MVC")
                strengths.append("Well-structured MVC pattern")
            else:
                weaknesses.append("Lacks clear architectural pattern")
                
            # Check for monolithic structure
            if len(py_files) > 500:
                weaknesses.append("Large number of files suggests potential monolithic structure")
                tech_debt = "medium"
                
            # Check for circular imports
            import_patterns = []
            for py_file in py_files:
                try:
                    content = py_file.read_text(encoding="utf-8")
                    # Look for imports
                    if "import" in content or "from" in content:
                        import_patterns.append(py_file.name)
                except:
                    pass
                    
            if len(set(import_patterns)) < len(import_patterns) * 0.3:  # Many duplicates
                weaknesses.append("Potential circular dependencies in imports")
        
        improvements = [
            "Refactor large modules into smaller components",
            "Implement proper error handling",
            "Add comprehensive test coverage",
            "Document public APIs",
            "Implement type annotations",
        ]
        
        return ArchitectureInsight(
            strengths=strengths,
            weaknesses=weaknesses,
            improvements=improvements,
            architectural_patterns=architectural_patterns,
            tech_debt=tech_debt,
        )

    def _generate_recommendations(self, insight: EngineeringInsight) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []
        
        # Requirements recommendations
        for req in insight.requirements:
            recommendations.append(f"Implement requirement {req.id}: {req.description}")
            
        # Defect recommendations
        for defect in insight.defects:
            recommendations.append(f"Fix defect {defect.id}: {defect.description}")
            
        # Architecture recommendations
        for pattern in insight.architecture.architectural_patterns:
            recommendations.append(f"Adopt {pattern} architectural pattern")
            
        for weakness in insight.architecture.weaknesses:
            recommendations.append(f"Address architectural weakness: {weakness}")
            
        recommendations.extend(insight.architecture.improvements)
        
        # Version recommendations based on defects
        if insight.defects:
            recommendations.append("Consider semantic version bump for bug fixes")
            
        return recommendations

    def _calculate_confidence(self, insight: EngineeringInsight) -> float:
        """Calculate confidence score based on analysis completeness."""
        # Simple scoring: more requirements + defects = higher confidence
        base_score = 0.3 * len(insight.requirements) + 0.5 * len(insight.defects)
        base_score = min(base_score, 1.0)  # Cap at 1.0
        return round(base_score, 2)

    def _persist_insight(self, insight: EngineeringInsight, project_id: str) -> None:
        """Store engineering insight in memory."""
        try:
            content = json.dumps({
                "requirements_count": len(insight.requirements),
                "defects_count": len(insight.defects),
                "confidence_score": insight.confidence_score,
                "architecture_strengths": insight.architecture.strengths,
                "architecture_weaknesses": insight.architecture.weaknesses,
                "architecture_improvements": insight.architecture.improvements,
                "architecture_tech_debt": insight.architecture.tech_debt,
            })
            store.save_memory(
                memory_type="engineering_insight",
                memory_key=f"insight_{project_id}",
                content=content,
                project_id=project_id,
                approved=True,
            )
        except Exception:
            pass


__all__ = [
    "EngineeringIntelligence",
    "Requirement",
    "Defect",
    "ArchitectureInsight",
    "EngineeringInsight",
]