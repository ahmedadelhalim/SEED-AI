import hashlib
import json
import threading
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Dict, Mapping, Optional

from security.permission_engine import ExecutionIdentity


class ApprovalError(RuntimeError):
    pass


class ApprovalExpiredError(ApprovalError):
    pass


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    principal_id: str
    identity_digest: str
    tool: str
    action: str
    scope: str
    arguments_digest: str
    created_at: datetime
    expires_at: datetime
    status: str = "pending"
    approved_by: Optional[str] = None


def _arguments_digest(arguments: Mapping[str, object]) -> str:
    encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _identity_digest(identity: ExecutionIdentity) -> str:
    encoded = json.dumps(identity.__dict__, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ApprovalManager:
    def __init__(self, default_ttl_seconds: int = 300, repository=None):
        if default_ttl_seconds < 1:
            raise ValueError("Approval lifetime must be positive")
        self.default_ttl_seconds = default_ttl_seconds
        self.repository = repository
        self._requests = {}  # type: Dict[str, ApprovalRequest]
        self._lock = threading.Lock()

    def request(self, tool: str, action: str, scope: str,
                arguments: Mapping[str, object],
                identity: Optional[ExecutionIdentity] = None,
                ttl_seconds: Optional[int] = None,
                now: Optional[datetime] = None) -> ApprovalRequest:
        lifetime = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if lifetime < 1:
            raise ValueError("Approval lifetime must be positive")
        current = now or datetime.now(timezone.utc)
        identity = identity or ExecutionIdentity()
        approval = ApprovalRequest(
            approval_id=uuid.uuid4().hex,
            principal_id=identity.principal_id,
            identity_digest=_identity_digest(identity),
            tool=tool,
            action=action,
            scope=scope,
            arguments_digest=_arguments_digest(arguments),
            created_at=current,
            expires_at=current + timedelta(seconds=lifetime),
        )
        with self._lock:
            self._requests[approval.approval_id] = approval
            if self.repository is not None:
                self.repository.save_approval_request({
                    "approval_id": approval.approval_id,
                    "principal_id": approval.principal_id,
                    "identity_digest": approval.identity_digest,
                    "identity_json": json.dumps(
                        identity.__dict__, sort_keys=True, separators=(",", ":")
                    ),
                    "tool": approval.tool,
                    "action": approval.action,
                    "scope": approval.scope,
                    "arguments_digest": approval.arguments_digest,
                    "status": approval.status,
                    "approved_by": approval.approved_by,
                    "created_at": approval.created_at.isoformat(),
                    "expires_at": approval.expires_at.isoformat(),
                })
        return approval

    def approve(self, approval_id: str, approved_by: str,
                now: Optional[datetime] = None) -> ApprovalRequest:
        if not approved_by:
            raise ValueError("Approver identity is required")
        current = now or datetime.now(timezone.utc)
        with self._lock:
            approval = self._load(approval_id)
            if approval is None:
                raise ApprovalError("Approval request was not found")
            if current >= approval.expires_at:
                expired = replace(approval, status="expired")
                self._requests[approval_id] = expired
                self._save_status(expired)
                raise ApprovalExpiredError("Approval request has expired")
            if approval.status != "pending":
                raise ApprovalError("Approval request is no longer pending")
            if self.repository is not None:
                record = self.repository.approve_request(
                    approval_id, approved_by, current.isoformat()
                )
                if record is None or record["status"] != "approved":
                    raise ApprovalError("Approval request is no longer pending")
            approved = replace(approval, status="approved", approved_by=approved_by)
            self._requests[approval_id] = approved
            return approved

    def consume(self, approval_id: str, tool: str, action: str, scope: str,
                arguments: Mapping[str, object],
                identity: Optional[ExecutionIdentity] = None,
                now: Optional[datetime] = None) -> bool:
        current = now or datetime.now(timezone.utc)
        identity = identity or ExecutionIdentity()
        with self._lock:
            approval = self._load(approval_id)
            if approval is None or approval.status != "approved":
                return False
            if current >= approval.expires_at:
                expired = replace(approval, status="expired")
                self._requests[approval_id] = expired
                self._save_status(expired)
                return False
            if (
                approval.principal_id != identity.principal_id
                or approval.identity_digest != _identity_digest(identity)
                or approval.tool != tool
                or approval.action != action
                or approval.scope != scope
                or approval.arguments_digest != _arguments_digest(arguments)
            ):
                return False
            if self.repository is not None and not self.repository.consume_approval_request(
                approval_id,
                identity.principal_id,
                _identity_digest(identity),
                tool,
                action,
                scope,
                _arguments_digest(arguments),
                current.isoformat(),
            ):
                return False
            self._requests[approval_id] = replace(approval, status="consumed")
            return True

    def get(self, approval_id: str) -> Optional[ApprovalRequest]:
        with self._lock:
            return self._load(approval_id)

    def _load(self, approval_id: str) -> Optional[ApprovalRequest]:
        approval = self._requests.get(approval_id)
        if approval is not None or self.repository is None:
            return approval
        row = self.repository.get_approval_request(approval_id)
        if row is None:
            return None
        approval = ApprovalRequest(
            approval_id=row["approval_id"],
            principal_id=row["principal_id"],
            identity_digest=row["identity_digest"],
            tool=row["tool"],
            action=row["action"],
            scope=row["scope"],
            arguments_digest=row["arguments_digest"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            status=row["status"],
            approved_by=row["approved_by"],
        )
        self._requests[approval_id] = approval
        return approval

    def _save_status(self, approval: ApprovalRequest):
        if self.repository is None:
            return
        self.repository.update_approval_status(
            approval.approval_id, approval.status, approval.approved_by
        )