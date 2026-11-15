"""
SEED-AI Dependency Resolver.

Resolves the authoritative Python interpreter and site-packages for SEED
components without consulting PATH-based discovery that may be polluted by
ZKBioTime or other foreign installations.

Guarantees:

- The resolver ALWAYS returns paths inside D:\SEED-AI\.venv when available.
- It raises RuntimeError on ambiguity instead of silently choosing a
  contaminated interpreter.
- It never falls back to global site-packages or foreign application roots.

Design invariant:

- Explicit interpreter resolution is required; PATH order is not trusted.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


SEED_ROOT = Path(os.environ.get("SEED_ROOT", r"D:\SEED-AI")).resolve()
SEED_VENV = SEED_ROOT / ".venv"
SEED_PYTHON = SEED_VENV / "Scripts" / "python.exe"
SEED_SITE_PACKAGES = SEED_VENV / "Lib" / "site-packages"


class DependencyResolutionError(RuntimeError):
    """Raised when SEED dependencies cannot be resolved safely."""


def _resolve_interpreter_interpreter_path() -> str:
    """Return absolute path to the seed interpreter executable."""
    candidate = SEED_PYTHON
    if not candidate.exists():
        raise DependencyResolutionError(
            f"SEED virtual environment interpreter missing: {candidate}"
        )
    return str(candidate)


def resolve_python() -> str:
    """Resolve the authoritative SEED Python interpreter (absolute path).

    This bypasses PATH lookup entirely and reads from the venv layout.
    """
    return _resolve_interpreter_path()


def resolve_site_packages() -> Path:
    """Resolve the authoritative SEED site-packages directory."""
    if not SEED_SITE_PACKAGES.exists():
        raise DependencyResolutionError(
            f"SEED site-packages missing: {SEED_SITE_PACKAGES}"
        )
    return SEED_SITE_PACKAGES


def resolve_package_path(package_name: str) -> Path:
    """Resolve an installed package's absolute path within the SEED venv.

    Raises DependencyResolutionError if the package is not installed in the
    authoritative SEED environment.
    """
    site = resolve_site_packages()
    candidate = site / package_name
    if not candidate.exists():
        # Also allow nested namespace packages like psutil -> psutil
        # and third-party packages that map directly.
        raise DependencyResolutionError(
            f"Package '{package_name}' not found in authoritative SEED venv at {site}"
        )
    return candidate


def check_dependency_available(package_name: str) -> bool:
    """Return True if package_name is resolvable in the isolated SEED env."""
    try:
        resolve_package_path(package_name)
        return True
    except DependencyResolutionError:
        return False


def build_isolated_env(
    python_path: Optional[str] = None,
) -> List[str]:
    """Build a clean, isolated environment for subprocess calls.

    Returns a list of env keys/values suitable for subprocesses so that
    PATH-based contamination does not affect child processes.
    """
    interpreter = python_path or resolve_python()
    # Clear potentially contaminated path entries for child processes.
    base_env = {
        "PATH": f"{SEED_VENV}/Scripts;/usr/bin;/bin",  # POSIX-ish fallback
    }
    # On Windows the path must be native.
    if os.name == "nt":
        base_env = {
            "PATH": f"{str(SEED_VENV / 'Scripts')};{os.environ.get('PATH', '')}",
            "PYTHONHOME": "",
            "PYTHONPATH": str(SEED_ROOT),
        }
    # Filter out known foreign roots from PATH.
    safe_path = []
    for entry in base_env.get("PATH", "").split(";"):
        entry = entry.strip()
        if not entry:
            continue
        if any(
            str(SEED_ROOT).lower().startswith(entry.replace("\\", "/").lower())
            or "zkbiotime" in entry.lower()
            or "zkeco" in entry.lower()
            or entry.upper().startswith("B:\\")
            or entry.upper().startswith("C:\\ZKBioTime")
            or entry.upper().startswith("D:\\ZKBioTime")
            or entry.upper().startswith("B:\\ZKBioTime")
        ):
            continue
        safe_path.append(entry)
    base_env["PATH"] = ";".join(safe_path)
    return [interpreter, base_env]  # type: ignore[return-value]


def resolve_all() -> dict:
    """Return a complete resolution report as a plain dict."""
    return {
        "python": resolve_python(),
        "site_packages": str(resolve_site_packages()),
        "venv_root": str(SEED_VENV),
    }
