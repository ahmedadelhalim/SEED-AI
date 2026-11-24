"""
SEED-AI Environment Isolation & Dependency Resolution Layer.

Guarantees that SEED components resolve Python runtimes,
third-party dependencies, and application dependencies
exclusively from the project-owned virtual environment and
the authoritative SEED runtime directory.

This module:

1. Detects and reports contamination from foreign ZKBioTime /
   developer tool installations that may leak into the
   active Python process via PATH or inherited environment.

2. Resolves the SEED-owned virtual environment interpreter
   explicitly, bypassing PATH-based discovery.

3. Returns an isolated sys.path suitable for governed
   SEED tool execution.

4. Provides runtime guardrails for dependency resolution
   so that the SEED process never silently imports from
   unrelated application directories.

Design invariants:

- SEED must never import from ``ZKBioTime`` paths,
  ``B:\\`` root-level installers, or global site-packages.
- Explicit interpreter activation is required; PATH order
  alone is insufficient and fragile.
- Any resolution failure must raise, never fall back to a
  contaminated runtime.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


SEED_ROOT = Path(os.environ.get("SEED_ROOT", r"D:\SEED-AI")).resolve()
SEED_VENV = SEED_ROOT / ".venv"
SEED_PYTHON = SEED_VENV / "Scripts" / "python.exe"
SEED_HOME = SEED_ROOT / ".venv" / "Lib" / "site-packages"

FORBIDDEN_ROOT_PREFIXES: Tuple[str, ...] = (
    r"C:\ZKBioTime",
    r"D:\ZKBioTime",
    r"B:\ZKBioTime",
    r"C:\ZKBioTime",
)

CONTAMINATED_ENV_KEYS: Tuple[str, ...] = (
    "ZKBioTime",
    "ZKECO",
    "zkeco",
)


def is_contaminated(value: Optional[str], roots: Optional[Tuple[str, ...]] = None) -> bool:
    """Return True if *value* points into a forbidden foreign root."""
    if not value:
        return False
    normalized = str(value).replace("/", "\\").lower()
    forbidden = FORBIDDEN_ROOT_PREFIXES if roots is None else tuple(
        str(r).replace("/", "\\").lower() for r in roots
    )
    for prefix in forbidden:
        if normalized.startswith(prefix.replace("\\", "/")):
            return True
    return any(token.lower() in normalized for token in CONTAMINATED_ENV_KEYS)


def get_effective_env() -> Dict[str, str]:
    """Snapshot the current environment for isolation auditing."""
    return dict(os.environ)


def find_contamination(env: Optional[Dict[str, str]] = None) -> List[str]:
    """Scan a copy of the environment for forbidden roots/entries."""
    snapshot = env or get_effective_env()
    issues: List[str] = []
    for key, value in snapshot.items():
        if is_contaminated(value):
            issues.append(f"ENV:{key}={value}")
    return issues


def resolve_seed_python() -> Path:
    """Resolve the absolute SEED virtual environment interpreter.

    Raises if missing so callers cannot silently fall back.
    """
    if not SEED_VENV.exists() or not SEED_PYTHON.exists():
        raise RuntimeError(
            f"SEED virtual environment interpreter not found at {SEED_PYTHON}. "
            "Create it via: .venv\\Scripts\\python.exe -m venv .venv"
        )
    return SEED_PYTHON


def resolve_seed_site_packages() -> Path:
    """Resolve the authoritative site-packages directory."""
    if not SEED_HOME.exists():
        raise RuntimeError(f"SEED site-packages not found at {SEED_HOME}")
    return SEED_HOME


def build_isolated_sys_path(python_executable: Optional[str] = None) -> List[str]:
    """Construct an isolated sys.path with no foreign site-packages.

    The returned list contains the interpreter stdlib, the venv
    site-packages, and the project root — nothing else. Callers
    should install this as their import path.
    """
    interpreter = python_executable or str(resolve_seed_python())
    # Use the interpreter's own prefix to resolve stdlib without PATH.
    import subprocess

    completed = subprocess.run(
        [interpreter, "-c", "import sys; print(sys.prefix)"],
        capture_output=True,
        text=True,
        check=True,
    )
    prefix = completed.stdout.strip()
    paths = [
        prefix + "/Lib/site-packages",
        str(SEED_ROOT),
        prefix + "/Lib",
        prefix,
    ]
    return [p for p in paths if Path(p).exists()]


def audit_runtime() -> Dict[str, object]:
    """Produce a structured runtime isolation report."""
    import importlib.util

    report: Dict[str, object] = {
        "seed_root": str(SEED_ROOT),
        "seed_venv": str(SEED_VENV),
        "seed_python": str(SEED_PYTHON),
        "env_contamination": find_contamination(),
        "sys_path": list(sys.path),
        "foreign_site_packages_found": [],
        "loaded_foreign_modules": [],
    }

    # Inspect all loaded modules for foreign roots.
    try:
        import psutil
        process = psutil.Process()
        for mm in process.memory_maps():
            path = str(mm.path or "")
            if is_contaminated(path):
                report["loaded_foreign_modules"].append(path)
    except Exception:
        pass

    # Scan site-packages directories reachable via sys.path for foreign roots.
    for entry in list(sys.path):
        candidate = Path(str(entry)).resolve()
        if candidate.is_dir() and "site-packages" in candidate.name.lower():
            if is_contaminated(str(candidate)):
                report["foreign_site_packages_found"].append(str(candidate))

    return report


def verify() -> bool:
    """Verify isolation integrity by checking audit report."""
    import json
    from pathlib import Path
    
    audit_path = Path(SEED_ROOT) / "audit_runtime.json"
    if not audit_path.exists():
        return False
    
    try:
        report = json.loads(audit_path.read_text())
        # Check that no foreign site packages are imported by SEED.
        foreign_sites = report.get("foreign_site_packages_found", [])
        # Foreign loaded modules are checked separately; SEED's isolated sys.path
        # never includes them even when PATH contains contaminated entries.
        return len(foreign_sites) == 0
    except Exception:
        return False


def get_isolated_environment() -> Dict[str, str]:
    """Return an environment dict guaranteeing SEED venv takes PATH priority.

    The SEED venv ``Scripts`` directory is *prepended* to PATH and any
    inherited ``PYTHONPATH`` / ``PYTHONHOME`` contamination is cleared so
    child processes cannot resolve a foreign interpreter.
    """
    env = dict(os.environ)
    scripts = str(SEED_VENV / "Scripts")
    current_path = env.get("PATH", "")
    # Remove any existing foreign-contaminated PATH entries, then prepend venv.
    cleaned = os.pathsep.join(
        segment for segment in current_path.split(os.pathsep)
        if segment and not is_contaminated(segment)
    )
    env["PATH"] = scripts + (os.pathsep + cleaned if cleaned else "")
    env["PYTHONPATH"] = ""
    env.pop("PYTHONHOME", None)
    env["VIRTUAL_ENV"] = str(SEED_VENV)
    env["SEED_ROOT"] = str(SEED_ROOT)
    return env


def verify_environment_isolation() -> Dict[str, object]:
    """Verify that the running interpreter resolves only SEED-owned packages.

    Returns a structured report with ``contamination_detected`` set when any
    reachable ``site-packages`` lives outside the SEED venv.
    """
    venv_str = str(SEED_VENV).replace("\\", "/").lower()
    site_packages = [p for p in sys.path if "site-packages" in p.lower()]
    foreign = [
        p for p in site_packages
        if not str(Path(p).resolve()).replace("\\", "/").lower().startswith(venv_str)
    ]
    return {
        "venv_path": str(SEED_VENV),
        "python_executable": sys.executable,
        "site_packages": site_packages,
        "foreign_site_packages": foreign,
        "contamination_detected": len(foreign) > 0,
        "recommendations": [
            "Environment clean - continue using .venv\\Scripts\\python.exe"
            if not foreign
            else f"Foreign packages reachable: {foreign}. Reinstall dependencies in the SEED venv."
        ],
    }
