"""
HLF Red-Hat Declaration Pathway — Layer 3 ethical governance.

Legitimate security research, penetration testing, and white-hat work are
SUPPORTED by HLF — not treated as suspicious.

Corporate AI blocks security researchers "for safety" and then wonders why
the security community can't get their jobs done.  HLF takes a different
stance:

  "If you declare it properly, we treat you as the professional you are."

A declaration:
  - Requires three mandatory fields (who, what scope, what authorization)
  - Creates a tamper-evident SHA-256 fingerprinted record
  - Stores attestations in-process (caller can persist to ALIGN ledger)
  - Does NOT whittle away the constitutional constraints — C-3 still blocks
    genuinely illegal acts even with a red-hat declaration.

Burden is on TRANSPARENCY, not on proving you're not a criminal.

People are the priority.  AI is the tool.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

# Required fields — documented so researchers know exactly what to provide
REQUIRED_FIELDS: list[str] = ["researcher_identity", "scope", "authorization"]

# Optional context fields (encouraged but not mandatory)
OPTIONAL_FIELDS: list[str] = [
    "timeframe",
    "target_systems",
    "ethics_review",
    "responsible_disclosure",
]


@dataclass
class Attestation:
    """Immutable record of a red-hat declaration."""
    researcher_identity: str
    scope: str
    authorization: str
    extra: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.fingerprint:
            payload = f"{self.researcher_identity}|{self.scope}|{self.authorization}|{self.created_at}"
            self.fingerprint = hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "researcher_identity": self.researcher_identity,
            "scope": self.scope,
            "authorization": self.authorization,
            "extra": self.extra,
            "created_at": self.created_at,
            "fingerprint": self.fingerprint,
        }


@dataclass
class VerificationResult:
    valid: bool
    reason: str = ""
    attestation: Attestation | None = None
    missing_fields: list[str] = field(default_factory=list)


# ── In-process attestation store ─────────────────────────────────────────────

_attestations: list[Attestation] = []


def get_attestations() -> list[dict[str, Any]]:
    """Return all recorded red-hat attestations (copies)."""
    return [a.to_dict() for a in _attestations]


# ── Public API ────────────────────────────────────────────────────────────────

def declare_research_intent(
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Register a security research declaration.

    Args:
        metadata: Dict that should contain REQUIRED_FIELDS plus any optional
                  context the researcher chooses to provide.

    Returns:
        Dict with keys: valid, reason, fingerprint, missing_fields.
    """
    result = verify_declaration(metadata)
    if result.valid and result.attestation:
        _attestations.append(result.attestation)
    return {
        "valid": result.valid,
        "reason": result.reason,
        "fingerprint": result.attestation.fingerprint if result.attestation else "",
        "missing_fields": result.missing_fields,
    }


def verify_declaration(metadata: dict[str, Any] | None) -> VerificationResult:
    """
    Verify a red-hat declaration is properly formed.

    Legitimate research is ASSUMED to be legitimate if declared properly.
    We don't demand proof — we demand transparency.
    """
    if not metadata:
        return VerificationResult(
            valid=False,
            reason="No declaration metadata provided.",
            missing_fields=list(REQUIRED_FIELDS),
        )

    missing = [f for f in REQUIRED_FIELDS if not metadata.get(f)]
    if missing:
        return VerificationResult(
            valid=False,
            reason=f"Declaration incomplete. Missing required fields: {', '.join(missing)}",
            missing_fields=missing,
        )

    extra = {k: v for k, v in metadata.items() if k not in REQUIRED_FIELDS}
    attestation = Attestation(
        researcher_identity=str(metadata["researcher_identity"]),
        scope=str(metadata["scope"]),
        authorization=str(metadata["authorization"]),
        extra=extra,
    )
    return VerificationResult(valid=True, attestation=attestation)


def is_declared(fingerprint: str) -> bool:
    """Check whether a given declaration fingerprint is on record."""
    return any(a.fingerprint == fingerprint for a in _attestations)


def latest_attestation() -> Attestation | None:
    """Return the most recent attestation, or None if none exist."""
    return _attestations[-1] if _attestations else None
