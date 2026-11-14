from typing import Any, Dict, List, Mapping, Tuple


CREATIVE_CAPABILITY_CATALOG = [
    {
        "category": "Image",
        "name": "Image generation & editing",
        "status": "unavailable",
        "description": "Text-to-image generation and advanced graphic design workflows.",
        "adapter": None,
    },
    {
        "category": "Video",
        "name": "Video editing & generation",
        "status": "unavailable",
        "description": "Text-to-video, motion graphics, and video rendering pipelines.",
        "adapter": None,
    },
    {
        "category": "Audio",
        "name": "Arabic & English STT/TTS",
        "status": "partial",
        "description": "Speech-to-text and text-to-speech media contracts defined; active audio runtimes not configured.",
        "adapter": "interfaces.media",
    },
    {
        "category": "3D",
        "name": "Blender & Unreal Engine integration",
        "status": "unavailable",
        "description": "3D asset creation and rendering pipelines.",
        "adapter": None,
    },
    {
        "category": "Development",
        "name": "Python, PowerShell & Git operations",
        "status": "operational",
        "description": "Workspace file management, system health diagnostics, and script execution via core tools.",
        "adapter": "core.operations, runtime.file_tools, runtime.windows.tools",
    },
    {
        "category": "Automation",
        "name": "Browser & OS automation",
        "status": "partial",
        "description": "Windows host discovery and file tools operational; Playwright browser automation planned.",
        "adapter": "runtime.windows.discovery, runtime.file_tools",
    },
    {
        "category": "AI",
        "name": "Central orchestration & plan engine",
        "status": "operational",
        "description": "SeedOrchestrator, TaskEngine, ToolRegistry, PermissionEngine, and PlanEngine.",
        "adapter": "core.orchestrator, core.plan_engine, core.planning",
    },
]


def list_capabilities() -> List[Dict[str, Any]]:
    return CREATIVE_CAPABILITY_CATALOG
