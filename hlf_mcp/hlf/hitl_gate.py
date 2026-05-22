"""
HITL (Human-in-the-Loop) Gate — blocks capsule VERIFY→MERGE until human approval.

Architecture:
    The gate is a file-based pending-approval queue. When a governed capsule
    completes inference and requires human approval, it writes an approval token
    to <state>/pending_approvals/<capsule_id>.json.

    The operator runs `hlf-operator approve --capsule-id` to sign off.
    Or `hlf-operator reject --capsule-id` to deny.

    Until approval, the capsule status is AWAITING_HUMAN_APPROVAL. After
    approval, it transitions to COMPLETED. After rejection, REJECTED_HUMAN.

State directory: hlf_mcp/state/pending_approvals/
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
HLF_STATE_DIR = os.environ.get("HLF_STATE_DIR")
if HLF_STATE_DIR:
    DEFAULT_PENDING_DIR = Path(HLF_STATE_DIR) / "pending_approvals"
else:
    DEFAULT_PENDING_DIR = REPO_ROOT / "state" / "pending_approvals"
DEFAULT_TIMEOUT_SECONDS = 600  # 10 minutes


@dataclass
class ApprovalRequest:
    """A single HITL approval request stored on disk."""
    capsule_id: str
    agent_id: str
    tier: str
    intent_summary: str
    output_preview: str              # first 200 chars of output
    manifest_hash: str
    output_hash: str
    gas_consumed: int
    gas_limit: int
    provenance_hashes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "AWAITING_HUMAN_APPROVAL"
    approved_by: str = ""
    approved_at: str = ""
    rejection_reason: str = ""
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def to_dict(self) -> dict[str, Any]:
        return {
            "capsule_id": self.capsule_id,
            "agent_id": self.agent_id,
            "tier": self.tier,
            "intent_summary": self.intent_summary,
            "output_preview": self.output_preview,
            "manifest_hash": self.manifest_hash,
            "output_hash": self.output_hash,
            "gas_consumed": self.gas_consumed,
            "gas_limit": self.gas_limit,
            "provenance_hashes": self.provenance_hashes,
            "created_at": self.created_at,
            "status": self.status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "rejection_reason": self.rejection_reason,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ApprovalRequest":
        return cls(
            capsule_id=d.get("capsule_id", ""),
            agent_id=d.get("agent_id", ""),
            tier=d.get("tier", "hearth"),
            intent_summary=d.get("intent_summary", ""),
            output_preview=d.get("output_preview", ""),
            manifest_hash=d.get("manifest_hash", ""),
            output_hash=d.get("output_hash", ""),
            gas_consumed=d.get("gas_consumed", 0),
            gas_limit=d.get("gas_limit", 0),
            provenance_hashes=d.get("provenance_hashes", []),
            created_at=d.get("created_at", ""),
            status=d.get("status", "AWAITING_HUMAN_APPROVAL"),
            approved_by=d.get("approved_by", ""),
            approved_at=d.get("approved_at", ""),
            rejection_reason=d.get("rejection_reason", ""),
            timeout_seconds=d.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
        )

    def is_expired(self) -> bool:
        """Check if this approval request has timed out."""
        if not self.created_at:
            return False
        try:
            created = datetime.fromisoformat(self.created_at)
            elapsed = (datetime.now(timezone.utc) - created).total_seconds()
            return elapsed > self.timeout_seconds
        except (ValueError, TypeError):
            return False


class HITLGate:
    """Human-in-the-Loop approval gate.

    Thread-safe singleton. Writes approval requests to disk as JSON files.
    The operator CLI reads these files to approve/reject.
    """

    _instance: HITLGate | None = None
    _lock = threading.Lock()

    def __init__(self, pending_dir: Path | None = None) -> None:
        self.pending_dir = pending_dir or DEFAULT_PENDING_DIR
        self.pending_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls, pending_dir: Path | None = None) -> "HITLGate":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(pending_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    def _request_path(self, capsule_id: str) -> Path:
        safe_id = capsule_id.replace("/", "_").replace("\\", "_").replace(":", "_")
        return self.pending_dir / f"{safe_id}.json"

    def submit_approval_request(self, request: ApprovalRequest) -> Path:
        """Write approval request to disk. Returns the file path."""
        path = self._request_path(request.capsule_id)
        with open(path, "w") as f:
            json.dump(request.to_dict(), f, indent=2)
        return path

    def approve(self, capsule_id: str, operator_id: str = "operator") -> ApprovalRequest:
        """Approve a pending capsule. Returns updated request.

        Raises:
            FileNotFoundError: No approval request exists for this capsule_id.
            ValueError: The request has already been finalized (rejected, completed, or expired).
        """
        path = self._request_path(capsule_id)
        if not path.exists():
            raise FileNotFoundError(f"No pending approval for capsule {capsule_id}")

        with open(path, "r") as f:
            data = json.load(f)

        request = ApprovalRequest.from_dict(data)
        if request.status in ("REJECTED_HUMAN", "REJECTED_TIMEOUT", "COMPLETED"):
            raise ValueError(
                f"Cannot approve capsule {capsule_id}: already finalized ({request.status})"
            )
        request.status = "COMPLETED"
        request.approved_by = operator_id
        request.approved_at = datetime.now(timezone.utc).isoformat()

        with open(path, "w") as f:
            json.dump(request.to_dict(), f, indent=2)

        return request

    def reject(self, capsule_id: str, reason: str, operator_id: str = "operator") -> ApprovalRequest:
        """Reject a pending capsule. Returns updated request.

        Raises:
            FileNotFoundError: No approval request exists for this capsule_id.
            ValueError: The request has already been finalized (rejected, completed, or expired).
        """
        path = self._request_path(capsule_id)
        if not path.exists():
            raise FileNotFoundError(f"No pending approval for capsule {capsule_id}")

        with open(path, "r") as f:
            data = json.load(f)

        request = ApprovalRequest.from_dict(data)
        if request.status in ("REJECTED_HUMAN", "REJECTED_TIMEOUT", "COMPLETED"):
            raise ValueError(
                f"Cannot reject capsule {capsule_id}: already finalized ({request.status})"
            )
        request.status = "REJECTED_HUMAN"
        request.approved_by = operator_id
        request.approved_at = datetime.now(timezone.utc).isoformat()
        request.rejection_reason = reason

        with open(path, "w") as f:
            json.dump(request.to_dict(), f, indent=2)

        return request

    def get_status(self, capsule_id: str) -> dict[str, Any] | None:
        """Get the current status of a pending approval."""
        path = self._request_path(capsule_id)
        if not path.exists():
            return None
        with open(path, "r") as f:
            return json.load(f)

    def list_pending(self) -> list[dict[str, Any]]:
        """List all pending approval requests."""
        results = []
        for f in sorted(self.pending_dir.glob("*.json")):
            try:
                with open(f, "r") as fp:
                    data = json.load(fp)
                if data.get("status") == "AWAITING_HUMAN_APPROVAL":
                    results.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def check_timeouts(self) -> list[ApprovalRequest]:
        """Check for expired approvals and auto-reject them."""
        expired = []
        for f in sorted(self.pending_dir.glob("*.json")):
            try:
                with open(f, "r") as fp:
                    data = json.load(fp)
                req = ApprovalRequest.from_dict(data)
                if req.status == "AWAITING_HUMAN_APPROVAL" and req.is_expired():
                    req.status = "REJECTED_TIMEOUT"
                    req.rejection_reason = f"Timed out after {req.timeout_seconds}s"
                    with open(f, "w") as fp:
                        json.dump(req.to_dict(), fp, indent=2)
                    expired.append(req)
            except (json.JSONDecodeError, OSError):
                continue
        return expired

    def is_approved(self, capsule_id: str) -> bool:
        """Check if a capsule has been approved."""
        status = self.get_status(capsule_id)
        if status is None:
            return False
        return status.get("status") == "COMPLETED"

    def is_rejected(self, capsule_id: str) -> bool:
        """Check if a capsule has been rejected."""
        status = self.get_status(capsule_id)
        if status is None:
            return False
        return status.get("status") in ("REJECTED_HUMAN", "REJECTED_TIMEOUT")

    def build_approval_token(self, request: ApprovalRequest) -> str:
        """Build a cryptographic approval token for the request."""
        payload = (
            f"{request.capsule_id}|{request.manifest_hash}|"
            f"{request.output_hash}|{request.created_at}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:24]


def require_human_approval(
    capsule_id: str,
    agent_id: str,
    tier: str,
    intent_summary: str,
    output_text: str,
    manifest_hash: str,
    output_hash: str,
    gas_consumed: int,
    gas_limit: int,
    provenance_hashes: list[str] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> ApprovalRequest:
    """Convenience function: submit a capsule for human approval.

    Call this from governed_latent_infer() or any inference path when
    the manifest has human_approval_required=True.

    Returns the ApprovalRequest that was written to disk.
    The caller should return AWAITING_HUMAN_APPROVAL status to the client.
    """
    gate = HITLGate.get_instance()
    request = ApprovalRequest(
        capsule_id=capsule_id,
        agent_id=agent_id,
        tier=tier,
        intent_summary=intent_summary[:200],
        output_preview=output_text[:200],
        manifest_hash=manifest_hash,
        output_hash=output_hash,
        gas_consumed=gas_consumed,
        gas_limit=gas_limit,
        provenance_hashes=provenance_hashes or [],
        timeout_seconds=timeout_seconds,
    )
    gate.submit_approval_request(request)
    return request
