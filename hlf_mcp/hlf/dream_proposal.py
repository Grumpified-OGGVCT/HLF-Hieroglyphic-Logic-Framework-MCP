"""
Dream Proposal — observe→propose→verify→promote gating bridge.

Connects dream cycle findings to the InstinctLifecycle state machine
through formalised promotion rules and CoVE gate enforcement.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from hlf_mcp.dream_cycle import DreamFinding


# ── Promotion rule enumeration ────────────────────────────────────────────────


class PromotionRule(Enum):
    """Promotion rule governing how a dream finding becomes binding."""

    AUTO_IF_CONFIDENCE = auto()   # confidence >= 0.85 auto-promotes
    MANUAL_APPROVAL = auto()      # requires explicit governor approval token
    GOVERNANCE_VOTE = auto()      # requires 3-of-5 validator signatures

    @classmethod
    def from_string(cls, value: str) -> PromotionRule:
        """Parse a promotion rule from string, case-insensitive."""
        mapping: dict[str, PromotionRule] = {
            "auto_if_confidence": cls.AUTO_IF_CONFIDENCE,
            "auto": cls.AUTO_IF_CONFIDENCE,
            "manual_approval": cls.MANUAL_APPROVAL,
            "manual": cls.MANUAL_APPROVAL,
            "governance_vote": cls.GOVERNANCE_VOTE,
            "governance": cls.GOVERNANCE_VOTE,
        }
        key = value.strip().lower().replace("-", "_")
        if key not in mapping:
            raise ValueError(
                f"Unknown promotion rule '{value}'. "
                f"Valid rules: {', '.join(mapping.keys())}"
            )
        return mapping[key]


# ── Dream proposal dataclass ──────────────────────────────────────────────────


@dataclass(slots=True)
class DreamProposal:
    """Formal proposal bridging a DreamFinding to the InstinctLifecycle."""

    proposal_id: str
    finding_id: str
    proposed_at: float
    status: str  # advisory, candidate, binding
    confidence: float
    evidence_refs: list[dict[str, Any]]
    promotion_rule: PromotionRule
    cove_result: dict[str, Any] | None = None
    promoted_at: float | None = None
    promoter: str = ""
    finding_title: str = ""
    finding_summary: str = ""
    finding_topic: str = ""
    candidate_actions: list[str] = field(default_factory=list)
    validator_signatures: list[str] = field(default_factory=list)
    governor_token: str = ""
    rejection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "finding_id": self.finding_id,
            "proposed_at": self.proposed_at,
            "status": self.status,
            "confidence": self.confidence,
            "evidence_refs": list(self.evidence_refs),
            "promotion_rule": self.promotion_rule.name,
            "cove_result": dict(self.cove_result) if self.cove_result else None,
            "promoted_at": self.promoted_at,
            "promoter": self.promoter,
            "finding_title": self.finding_title,
            "finding_summary": self.finding_summary,
            "finding_topic": self.finding_topic,
            "candidate_actions": list(self.candidate_actions),
            "validator_signatures": list(self.validator_signatures),
            "governor_token": self.governor_token,
            "rejection_reason": self.rejection_reason,
        }

    def is_advisory(self) -> bool:
        return self.status == "advisory"

    def is_candidate(self) -> bool:
        return self.status == "candidate"

    def is_binding(self) -> bool:
        return self.status == "binding"

    def evaluate_promotion_rule(
        self,
        *,
        cove_passed: bool,
        governor_token: str = "",
        validator_signatures: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Evaluate whether this proposal can be promoted under its rule.

        Returns (eligible, reason).
        """
        if not cove_passed:
            return False, "cove_gate_not_passed"

        rule = self.promotion_rule

        if rule == PromotionRule.AUTO_IF_CONFIDENCE:
            if self.confidence >= 0.85:
                return True, "auto_promoted_confidence_threshold"
            return False, f"confidence_below_threshold ({self.confidence:.2f} < 0.85)"

        if rule == PromotionRule.MANUAL_APPROVAL:
            if governor_token and _validate_governor_token(governor_token):
                return True, "manual_approval_granted"
            return False, "governor_token_required"

        if rule == PromotionRule.GOVERNANCE_VOTE:
            sigs = validator_signatures or self.validator_signatures
            valid_sigs = _count_valid_signatures(sigs)
            if valid_sigs >= 3:
                return True, f"governance_vote_passed ({valid_sigs}/5)"
            return False, f"governance_vote_insufficient ({valid_sigs}/5, need 3)"

        return False, "unknown_promotion_rule"


# ── Proposal factory ──────────────────────────────────────────────────────────


def create_dream_proposal(
    finding: DreamFinding,
    *,
    promotion_rule: PromotionRule = PromotionRule.AUTO_IF_CONFIDENCE,
) -> DreamProposal:
    """Create a DreamProposal from a DreamFinding.

    Maps all relevant finding fields into the proposal structure.
    """
    proposal_id = _digest_proposal_id(finding.finding_id, finding.cycle_id)
    return DreamProposal(
        proposal_id=proposal_id,
        finding_id=finding.finding_id,
        proposed_at=time.time(),
        status="advisory",
        confidence=finding.confidence,
        evidence_refs=list(finding.evidence_refs),
        promotion_rule=promotion_rule,
        cove_result=None,
        promoted_at=None,
        promoter="",
        finding_title=finding.title,
        finding_summary=finding.summary,
        finding_topic=finding.topic,
        candidate_actions=list(finding.candidate_actions),
        validator_signatures=[],
        governor_token="",
        rejection_reason="",
    )


def promote_to_candidate(
    proposal: DreamProposal,
    *,
    cove_result: dict[str, Any] | None = None,
    governor_token: str = "",
    validator_signatures: list[str] | None = None,
) -> tuple[DreamProposal, bool, str]:
    """Attempt to promote a proposal from advisory to candidate.

    Requires CoVE gate pass plus meeting the promotion rule.

    Returns (updated_proposal, success, reason).
    """
    if proposal.status != "advisory":
        return proposal, False, f"cannot promote from status '{proposal.status}'"

    # CoVE gate must pass
    cove_passed = _check_cove_gate(cove_result)
    if not cove_passed:
        proposal.rejection_reason = "cove_gate_failed"
        return proposal, False, "cove_gate_failed"

    proposal.cove_result = dict(cove_result) if cove_result else {"passed": True}

    # Evaluate promotion rule
    eligible, reason = proposal.evaluate_promotion_rule(
        cove_passed=True,
        governor_token=governor_token,
        validator_signatures=validator_signatures,
    )

    if not eligible:
        proposal.rejection_reason = reason
        return proposal, False, reason

    # Promote to candidate
    proposal.status = "candidate"
    proposal.promoted_at = time.time()
    proposal.promoter = "cove_gate"
    if governor_token:
        proposal.governor_token = governor_token
        proposal.promoter = "governor"
    if validator_signatures:
        proposal.validator_signatures = list(validator_signatures)
        proposal.promoter = "governance_validators"

    return proposal, True, reason


def promote_to_binding(
    proposal: DreamProposal,
    *,
    cove_result: dict[str, Any] | None = None,
    governor_token: str = "",
    validator_signatures: list[str] | None = None,
) -> tuple[DreamProposal, bool, str]:
    """Attempt to promote a proposal from candidate to binding.

    Requires CoVE gate pass plus meeting the promotion rule.
    """
    if proposal.status != "candidate":
        return proposal, False, f"cannot promote to binding from status '{proposal.status}'"

    # CoVE gate must pass
    cove_passed = _check_cove_gate(cove_result)
    if not cove_passed:
        proposal.rejection_reason = "cove_gate_failed_binding"
        return proposal, False, "cove_gate_failed"

    if cove_result:
        proposal.cove_result = dict(cove_result)

    # Evaluate promotion rule (stricter for binding)
    eligible, reason = proposal.evaluate_promotion_rule(
        cove_passed=True,
        governor_token=governor_token,
        validator_signatures=validator_signatures,
    )

    if not eligible:
        proposal.rejection_reason = reason
        return proposal, False, reason

    proposal.status = "binding"
    proposal.promoted_at = time.time()
    if governor_token:
        proposal.governor_token = governor_token
        proposal.promoter = "governor"
    if validator_signatures:
        proposal.validator_signatures = list(validator_signatures)
        proposal.promoter = "governance_validators"

    return proposal, True, reason


# ── Helpers ───────────────────────────────────────────────────────────────────


def _digest_proposal_id(finding_id: str, cycle_id: str) -> str:
    payload = f"{finding_id}|{cycle_id}|{time.time()}"
    return f"proposal-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _validate_governor_token(token: str) -> bool:
    """Validate a governor approval token.

    Tokens must be non-empty and follow the format: gov-<hex16>
    """
    if not token or not isinstance(token, str):
        return False
    if not token.startswith("gov-"):
        return False
    suffix = token[4:]
    if len(suffix) != 16:
        return False
    try:
        int(suffix, 16)
        return True
    except ValueError:
        return False


def _count_valid_signatures(signatures: list[str]) -> int:
    """Count valid validator signatures.

    Valid signatures are non-empty hex strings (64 chars for SHA-256).
    """
    valid = 0
    seen: set[str] = set()
    for sig in signatures:
        if not sig or not isinstance(sig, str):
            continue
        if sig in seen:
            continue
        if len(sig) == 64:
            try:
                int(sig, 16)
                seen.add(sig)
                valid += 1
            except ValueError:
                pass
    return valid


def _check_cove_gate(cove_result: dict[str, Any] | None) -> bool:
    """Check if a CoVE verification result indicates a pass."""
    if cove_result is None:
        return False
    if cove_result.get("passed") is True:
        return True
    if cove_result.get("all_proven") is True:
        return True
    verdict = str(cove_result.get("verdict", "")).upper()
    if verdict in {"APPROVED", "PASSED", "PROVEN"}:
        return True
    return False


def create_governor_token() -> str:
    """Generate a valid governor approval token."""
    return f"gov-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]}"


def create_validator_signature(validator_id: str) -> str:
    """Generate a valid validator signature."""
    payload = f"{validator_id}|{time.time()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
