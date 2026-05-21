"""Proof artifact format standardization for formal verification.

Provides:
- ProofStatus enum: admitted, denied, unverified, timeout, error
- ProofArtifact dataclass with full verification metadata
- Helper functions: create, admit, deny, format report
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ProofStatus(str, Enum):
    """Canonical proof status for verification artifacts."""
    ADMITTED = "admitted"
    DENIED = "denied"
    UNVERIFIED = "unverified"
    TIMEOUT = "timeout"
    ERROR = "error"


# Canonical operator classes for Z3 coverage tracking
OPERATOR_CLASSES: tuple[str, ...] = (
    "arithmetic",
    "comparison",
    "boolean",
    "set",
    "control_flow",
    "type_coercion",
)


@dataclass(slots=True)
class ProofArtifact:
    """A structured proof artifact for formal verification results.

    Encodes the complete verification lifecycle: theorem, formula,
    Z3 result, model, proof trace, timing, and extensible evidence.
    """

    artifact_id: str  # UUID
    operator_class: str  # "arithmetic" | "comparison" | "boolean" | "set" | "control_flow" | "type_coercion"
    theorem: str  # Human-readable theorem statement
    formula: str  # SMT-LIB / Z3 formula
    status: ProofStatus
    result: str | None  # "sat", "unsat", "unknown", or error message
    model: dict[str, Any] | None  # Counterexample model if sat
    proof_trace: str | None  # Z3 proof trace if unsat
    time_ms: float
    created_at: str  # ISO timestamp
    admitted_by: str | None  # "z3" | "manual" | "regression"
    evidence: dict[str, Any]  # Extensible metadata

    def to_dict(self) -> dict[str, Any]:
        """Serialize the proof artifact to a dictionary."""
        return {
            "artifact_id": self.artifact_id,
            "operator_class": self.operator_class,
            "theorem": self.theorem,
            "formula": self.formula,
            "status": self.status.value,
            "result": self.result,
            "model": self.model,
            "proof_trace": self.proof_trace,
            "time_ms": self.time_ms,
            "created_at": self.created_at,
            "admitted_by": self.admitted_by,
            "evidence": self.evidence,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)


# ── Factory and lifecycle functions ────────────────────────────────────────


def create_proof_artifact(
    operator_class: str,
    theorem: str,
    formula: str,
    result: str | None = None,
    *,
    model: dict[str, Any] | None = None,
    proof_trace: str | None = None,
    time_ms: float = 0.0,
    evidence: dict[str, Any] | None = None,
) -> ProofArtifact:
    """Create a ProofArtifact from verification data.

    Args:
        operator_class: The operator class being verified.
        theorem: Human-readable theorem statement.
        formula: SMT-LIB / Z3 formula string.
        result: Z3 result string ("sat", "unsat", "unknown") or error message.
        model: Counterexample model dict if result is "sat".
        proof_trace: Z3 proof trace if result is "unsat".
        time_ms: Verification time in milliseconds.
        evidence: Extensible metadata dict.

    Returns:
        A ProofArtifact with status=UNVERIFIED initially.
    """
    return ProofArtifact(
        artifact_id=str(uuid.uuid4()),
        operator_class=operator_class,
        theorem=theorem,
        formula=formula,
        status=ProofStatus.UNVERIFIED,
        result=result,
        model=model,
        proof_trace=proof_trace,
        time_ms=time_ms,
        created_at=datetime.now(timezone.utc).isoformat(),
        admitted_by=None,
        evidence=evidence if evidence is not None else {},
    )


def admit_proof(artifact: ProofArtifact, admitted_by: str = "z3") -> ProofArtifact:
    """Admit a proof artifact, setting status to ADMITTED.

    Args:
        artifact: The proof artifact to admit.
        admitted_by: Who/what admitted the proof ("z3", "manual", "regression").

    Returns:
        The updated ProofArtifact.
    """
    artifact.status = ProofStatus.ADMITTED
    artifact.admitted_by = admitted_by
    artifact.created_at = datetime.now(timezone.utc).isoformat()
    return artifact


def deny_proof(artifact: ProofArtifact, reason: str) -> ProofArtifact:
    """Deny a proof artifact, setting status to DENIED.

    Args:
        artifact: The proof artifact to deny.
        reason: Why the proof was denied.

    Returns:
        The updated ProofArtifact.
    """
    artifact.status = ProofStatus.DENIED
    artifact.evidence["denial_reason"] = reason
    artifact.created_at = datetime.now(timezone.utc).isoformat()
    return artifact


def format_proof_report(artifacts: list[ProofArtifact]) -> dict[str, Any]:
    """Format a summary report from a list of proof artifacts.

    Args:
        artifacts: List of ProofArtifact instances.

    Returns:
        A dict with total, admitted, denied, unverified, timeout, error
        counts plus a per-class breakdown.
    """
    total = len(artifacts)
    admitted = sum(1 for a in artifacts if a.status == ProofStatus.ADMITTED)
    denied = sum(1 for a in artifacts if a.status == ProofStatus.DENIED)
    unverified = sum(1 for a in artifacts if a.status == ProofStatus.UNVERIFIED)
    timeout = sum(1 for a in artifacts if a.status == ProofStatus.TIMEOUT)
    error = sum(1 for a in artifacts if a.status == ProofStatus.ERROR)

    per_class: dict[str, dict[str, int]] = {}
    for cls_name in OPERATOR_CLASSES:
        cls_artifacts = [a for a in artifacts if a.operator_class == cls_name]
        if cls_artifacts:
            per_class[cls_name] = {
                "total": len(cls_artifacts),
                "admitted": sum(1 for a in cls_artifacts if a.status == ProofStatus.ADMITTED),
                "denied": sum(1 for a in cls_artifacts if a.status == ProofStatus.DENIED),
                "unverified": sum(1 for a in cls_artifacts if a.status == ProofStatus.UNVERIFIED),
                "timeout": sum(1 for a in cls_artifacts if a.status == ProofStatus.TIMEOUT),
                "error": sum(1 for a in cls_artifacts if a.status == ProofStatus.ERROR),
            }
        else:
            per_class[cls_name] = {
                "total": 0,
                "admitted": 0,
                "denied": 0,
                "unverified": 0,
                "timeout": 0,
                "error": 0,
            }

    return {
        "total": total,
        "admitted": admitted,
        "denied": denied,
        "unverified": unverified,
        "timeout": timeout,
        "error": error,
        "per_class": per_class,
    }
