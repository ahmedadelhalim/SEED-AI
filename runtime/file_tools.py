import fnmatch
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.workspace_guard import validate_path, WORKSPACE


DEFAULT_EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "link_test",
}

DEFAULT_EXCLUDED_FILE_PATTERNS = [
    "*.pem",
    "*.key",
    "*.pfx",
    "*.db",
    "*.sqlite*",
    "*.enc",
    "id_rsa*",
    "credentials*",
    "secrets*",
    ".env*",
]

MAX_READ_BYTES = 1024 * 1024  # 1 MB max upper bound
DEFAULT_READ_BYTES = 256 * 1024  # 256 KB default
MAX_WRITE_BYTES = 2 * 1024 * 1024  # 2 MB max write
MAX_SEARCH_FILES = 500
MAX_SEARCH_RESULTS = 100
DEFAULT_SEARCH_RESULTS = 50
SEARCH_TIMEOUT_SECONDS = 5.0


class FileTools:
    """Governed filesystem tools strictly restricted to the authorized workspace."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or WORKSPACE

    def read(self, relative_path: str,
             start_line: Optional[int] = None,
             end_line: Optional[int] = None,
             max_bytes: Optional[int] = None) -> Dict[str, Any]:
        target = validate_path(relative_path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        if not target.is_file():
            raise ValueError(f"Path is not a regular file: {relative_path}")

        file_size = target.stat().st_size
        effective_max_bytes = min(max_bytes or DEFAULT_READ_BYTES, MAX_READ_BYTES)

        with target.open("rb") as handle:
            raw_data = handle.read(effective_max_bytes + 1)

        truncated = len(raw_data) > effective_max_bytes
        if truncated:
            raw_data = raw_data[:effective_max_bytes]

        text = raw_data.decode("utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        total_lines = len(lines)

        actual_start = 1
        actual_end = total_lines

        if start_line is not None or end_line is not None:
            start_idx = max((start_line or 1) - 1, 0)
            end_idx = min(end_line or total_lines, total_lines)
            if start_idx > end_idx:
                sliced_lines = []
            else:
                sliced_lines = lines[start_idx:end_idx]
            text = "".join(sliced_lines)
            actual_start = start_idx + 1 if sliced_lines else (start_line or 1)
            actual_end = start_idx + len(sliced_lines)

        return {
            "status": "success",
            "relative_path": relative_path,
            "content": text,
            "total_lines": total_lines,
            "start_line": actual_start,
            "end_line": actual_end,
            "bytes_read": len(text.encode("utf-8")),
            "file_size_bytes": file_size,
            "truncated": truncated,
        }

    def search(self, pattern: str,
               relative_path: str = ".",
               file_pattern: Optional[str] = None,
               max_results: int = DEFAULT_SEARCH_RESULTS) -> Dict[str, Any]:
        if not pattern:
            raise ValueError("Search pattern cannot be empty")

        target_dir = validate_path(relative_path)
        if not target_dir.exists():
            raise FileNotFoundError(f"Directory not found: {relative_path}")
        if not target_dir.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {relative_path}")

        limit = min(max(max_results, 1), MAX_SEARCH_RESULTS)
        matches: List[Dict[str, Any]] = []
        files_scanned = 0
        truncated = False
        deadline = time.monotonic() + SEARCH_TIMEOUT_SECONDS
        pattern_lower = pattern.lower()

        for root, dirs, files in os.walk(str(target_dir)):
            if time.monotonic() >= deadline:
                truncated = True
                break

            # Exclude sensitive/build directories in-place
            dirs[:] = [
                d for d in dirs
                if d not in DEFAULT_EXCLUDED_DIRS and not d.startswith(".")
            ]

            for filename in sorted(files):
                if time.monotonic() >= deadline:
                    truncated = True
                    break

                # Exclude sensitive file patterns
                if any(fnmatch.fnmatch(filename.lower(), pat.lower()) for pat in DEFAULT_EXCLUDED_FILE_PATTERNS):
                    continue

                if file_pattern and not fnmatch.fnmatch(filename.lower(), file_pattern.lower()):
                    continue

                file_path = Path(root) / filename
                try:
                    rel_to_workspace = file_path.resolve().relative_to(WORKSPACE)
                    rel_str = str(rel_to_workspace).replace("\\", "/")
                except ValueError:
                    continue

                files_scanned += 1
                if files_scanned > MAX_SEARCH_FILES:
                    truncated = True
                    break

                # Match against filename
                if pattern_lower in filename.lower():
                    matches.append({
                        "type": "filename",
                        "file": rel_str,
                        "line_number": None,
                        "line": filename,
                    })
                    if len(matches) >= limit:
                        truncated = True
                        break

                # Match against content if within size limit (< 1 MB)
                try:
                    stat = file_path.stat()
                    if stat.st_size > 1024 * 1024:
                        continue

                    with file_path.open("r", encoding="utf-8", errors="replace") as f:
                        for line_num, line in enumerate(f, start=1):
                            if pattern_lower in line.lower():
                                matches.append({
                                    "type": "content",
                                    "file": rel_str,
                                    "line_number": line_num,
                                    "line": line.strip()[:200],
                                })
                                if len(matches) >= limit:
                                    truncated = True
                                    break
                except (OSError, UnicodeDecodeError):
                    continue

                if len(matches) >= limit:
                    break

            if len(matches) >= limit or files_scanned > MAX_SEARCH_FILES:
                break

        return {
            "status": "success",
            "pattern": pattern,
            "matches": matches,
            "count": len(matches),
            "files_scanned": files_scanned,
            "truncated": truncated,
        }

    def write(self, relative_path: str, content: str,
              allow_overwrite: bool = False) -> Dict[str, Any]:
        if not isinstance(content, str):
            raise ValueError("Content must be a string")
        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            raise ValueError(f"Content exceeds maximum allowed write size of {MAX_WRITE_BYTES} bytes")

        target = validate_path(relative_path)

        file_existed = target.exists()
        if file_existed:
            if target.is_dir():
                raise IsADirectoryError(f"Target path is an existing directory: {relative_path}")
            if not allow_overwrite:
                raise FileExistsError(
                    f"File already exists: {relative_path}. Explicit authorization (allow_overwrite=True) is required to overwrite."
                )

        target.parent.mkdir(parents=True, exist_ok=True)

        temp_name = f".tmp_{uuid.uuid4().hex}_{target.name}"
        temp_path = target.parent / temp_name

        try:
            with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())

            # Atomic replace
            temp_path.replace(target)
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise

        return {
            "status": "success",
            "relative_path": relative_path,
            "bytes_written": len(content.encode("utf-8")),
            "overwritten": file_existed,
        }
