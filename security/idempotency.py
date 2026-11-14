import threading
from typing import Any, Callable, Dict, Tuple


class DuplicateExecutionError(RuntimeError):
    pass


class IdempotencyConflictError(RuntimeError):
    pass


class IdempotencyGuard:
    def __init__(self, repository=None):
        self.repository = repository
        self._completed = {}  # type: Dict[str, Any]
        self._in_progress = set()
        self._lock = threading.Lock()

    def execute(self, key: str, operation: Callable[[], Any],
                fingerprint: str = None) -> Tuple[Any, bool]:
        if not key:
            raise ValueError("Idempotency key is required")
        fingerprint = fingerprint or key
        with self._lock:
            if key in self._completed:
                return self._completed[key], True
            if key in self._in_progress:
                raise DuplicateExecutionError("An execution with this key is in progress")
            self._in_progress.add(key)

        if self.repository is not None:
            status, cached = self.repository.claim_idempotency(key, fingerprint)
            if status == "completed":
                with self._lock:
                    self._in_progress.discard(key)
                    self._completed[key] = cached
                return cached, True
            if status != "claimed":
                with self._lock:
                    self._in_progress.discard(key)
                if status == "conflict":
                    raise IdempotencyConflictError(
                        "Idempotency key was already used for a different operation"
                    )
                raise DuplicateExecutionError(
                    "An execution with this key is in progress"
                )

        try:
            result = operation()
        except Exception:
            with self._lock:
                self._in_progress.discard(key)
            if self.repository is not None:
                self.repository.release_idempotency(key, fingerprint)
            raise

        with self._lock:
            self._in_progress.discard(key)
            if isinstance(result, dict) and result.get("status") == "success":
                self._completed[key] = result
                if self.repository is not None:
                    self.repository.complete_idempotency(
                        key, fingerprint, result
                    )
            elif self.repository is not None:
                self.repository.release_idempotency(key, fingerprint)
        return result, False