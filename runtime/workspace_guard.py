
import os
from pathlib import Path

WORKSPACE = Path(os.environ.get(
    "SEED_WORKSPACE_PATH", "D:/SEED-AI/workspace"
)).resolve(strict=True)


def validate_path(relative_path: str) -> Path:
    requested = Path(relative_path)

    if requested.is_absolute():
        raise PermissionError("Absolute paths are not allowed")

    if ".." in requested.parts:
        raise PermissionError("Path traversal is not allowed")

    candidate = WORKSPACE / requested

    # Resolve existing components to detect links leaving the workspace.
    target = candidate.resolve(strict=False)

    try:
        target.relative_to(WORKSPACE)
    except ValueError:
        raise PermissionError("Access outside workspace denied")

    # Reject any existing symbolic link in the requested path.
    current = WORKSPACE
    for part in requested.parts:
        current = current / part
        if current.is_symlink():
            raise PermissionError("Symbolic links are not allowed")

    return target


if __name__ == "__main__":
    tests = [
        "notes/test.txt",
        "../Windows/system.ini",
        "D:/Windows/system.ini",
        "link_test/external/system.ini",
    ]

    for item in tests:
        try:
            result = validate_path(item)
            print("ALLOWED:", item, "->", result)
        except (PermissionError, OSError) as error:
            print("DENIED:", item, "|", error)
