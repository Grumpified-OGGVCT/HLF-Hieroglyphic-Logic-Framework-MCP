"""Cross-Witness Agreement Proofs — Byzantine-tolerant multi-agent knowledge verification.

Provides:
- CrossWitnessProver: proves agreement/disagreement with confidence scores
- QuorumPolicy: configurable agreement thresholds
- DisagreementResolver: structured disagreement reports with resolution strategies
- Byzantine tolerance: handles up to f faulty witnesses out of 3f+1 total
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from hlf_mcp.hlf.witness_governance import (
    TrustState,
    TrustStateSnapshot,
    WitnessObservation,
)


# ---------------------------------------------------------------------------
# Quorum Policy
# ---------------------------------------------------------------------------

class QuorumPolicy(Enum):
    """Configurable agreement thresholds for cross-witness verification."""
    SIMPLE_MAJORITY = auto()       # > 50% of witnesses must agree
    SUPERMAJORITY = auto()         # >= 67% (2/3) of witnesses must agree
    UNANIMOUS = auto()             # 100% of witnesses must agree
    WEIGHTED_BY_PROFICIENCY = auto()  # weighted by agent proficiency scores

    def threshold(self, total_witnesses: int) -> int:
        """Return the minimum number of agreeing witnesses required.

        Args:
            total_witnesses: Total number of witnesses being evaluated.

        Returns:
            Minimum agreeing witnesses needed to satisfy this policy.
        """
        if total_witnesses <= 0:
            return 0
        if self == QuorumPolicy.SIMPLE_MAJORITY:
            return (total_witnesses // 2) + 1
        if self == QuorumPolicy.SUPERMAJORITY:
            return int(total_witnesses * 2 / 3) + 1
        if self == QuorumPolicy.UNANIMOUS:
            return total_witnesses
        # WEIGHTED_BY_PROFICIENCY — handled differently, minimum is simple majority
        return (total_witnesses // 2) + 1

    def describe(self) -> str:
        return {
            QuorumPolicy.SIMPLE_MAJORITY: "Simple majority (>50% agreement)",
            QuorumPolicy.SUPERMAJORITY: "Supermajority (>=67% agreement)",
            QuorumPolicy.UNANIMOUS: "Unanimous (100% agreement)",
            QuorumPolicy.WEIGHTED_BY_PROFICIENCY: "Weighted by agent proficiency",
        }[self]


# ---------------------------------------------------------------------------
# Disagreement Resolution
# ---------------------------------------------------------------------------

class ResolutionStrategy(Enum):
    """Strategies for resolving witness disagreements."""
    DEFER_HIGHEST_PROFICIENCY = auto()
    RERUN_WITH_MORE_GAS = auto()
    FLAG_FOR_OPERATOR = auto()
    MAJORITY_VOTE = auto()
    REQUIRE_CORROBORATION = auto()


@dataclass(slots=True)
class DisagreementReport:
    """Structured report when witnesses disagree on a knowledge claim.

    Attributes:
        has_disagreement: Whether any disagreement was detected.
        agreeing_count: Number of witnesses in agreement.
        disagreeing_count: Number of witnesses in disagreement.
        total_witnesses: Total witnesses evaluated.
        quorum_policy: The policy used for evaluation.
        quorum_met: Whether the quorum threshold was met.
        confidence: Aggregate confidence in the majority position (0.0 - 1.0).
        byzantine_faults: Number of witnesses flagged as potentially Byzantine.
        resolution_strategy: Recommended strategy to resolve the disagreement.
        detail: Per-witness breakdown.
        resolution_guidance: Human-readable resolution steps.
    """

    has_disagreement: bool
    agreeing_count: int
    disagreeing_count: int
    total_witnesses: int
    quorum_policy: str
    quorum_met: bool
    confidence: float
    byzantine_faults: int
    resolution_strategy: str
    detail: list[dict[str, Any]] = field(default_factory=list)
    resolution_guidance: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_disagreement": self.has_disagreement,
            "agreeing_count": self.agreeing_count,
            "disagreeing_count": self.disagreeing_count,
            "total_witnesses": self.total_witnesses,
            "quorum_policy": self.quorum_policy,
            "quorum_met": self.quorum_met,
            "confidence": self.confidence,
            "byzantine_faults": self.byzantine_faults,
            "resolution_strategy": self.resolution_strategy,
            "detail": self.detail,
            "resolution_guidance": self.resolution_guidance,
        }


class DisagreementResolver:
    """Resolves witness disagreements with structured strategies.

    When independent agents produce conflicting knowledge claims, this
    resolver produces a disagreement report with concrete resolution
    strategies and operator guidance.
    """

    def __init__(
        self,
        default_strategy: ResolutionStrategy = ResolutionStrategy.MAJORITY_VOTE,
    ) -> None:
        self._default_strategy = default_strategy

    def resolve(
        self,
        witnesses: list[dict[str, Any]],
        quorum_policy: QuorumPolicy = QuorumPolicy.SIMPLE_MAJORITY,
        agent_proficiencies: dict[str, float] | None = None,
    ) -> DisagreementReport:
        """Resolve disagreement among a set of witness claims.

        Each witness dict must have at minimum:
        - ``witness_id``: str — unique witness identifier
        - ``claim_hash``: str — content hash of their claim
        - ``confidence``: float — self-reported confidence (0.0-1.0)
        - ``trust_state``: str — one of healthy/watched/probation/restricted

        Args:
            witnesses: List of witness claim dicts.
            quorum_policy: The agreement threshold policy.
            agent_proficiencies: Optional dict of agent_id → proficiency score (0.0-1.0).

        Returns:
            DisagreementReport with full analysis.
        """
        if not witnesses:
            return DisagreementReport(
                has_disagreement=False,
                agreeing_count=0,
                disagreeing_count=0,
                total_witnesses=0,
                quorum_policy=quorum_policy.name,
                quorum_met=True,
                confidence=1.0,
                byzantine_faults=0,
                resolution_strategy="N/A — no witnesses",
                detail=[],
                resolution_guidance="No witnesses provided — cannot evaluate agreement.",
            )

        total = len(witnesses)
        # Determine the majority claim hash
        claim_votes = self._tally_claims(witnesses, agent_proficiencies, quorum_policy)
        majority_claim = claim_votes["majority_claim"]
        majority_votes = claim_votes["majority_votes"]
        minority_votes = total - majority_votes

        # Byzantine fault detection
        byzantine = self._detect_byzantine(witnesses, majority_claim, total)

        # Assess quorum
        quorum_met = majority_votes >= quorum_policy.threshold(total)

        # Build per-witness detail
        detail = self._build_detail(witnesses, majority_claim, agent_proficiencies)

        # Determine resolution strategy
        resolution_strategy, resolution_guidance = self._determine_strategy(
            quorum_met=quorum_met,
            byzantine_count=len(byzantine),
            total=total,
            quorum_policy=quorum_policy,
            agent_proficiencies=agent_proficiencies,
            witnesses=witnesses,
        )

        # Confidence: weighted by quorum ratio and witness trust
        if agent_proficiencies and quorum_policy == QuorumPolicy.WEIGHTED_BY_PROFICIENCY:
            confidence = claim_votes["weighted_agreement_ratio"]
        else:
            trust_penalty = (
                sum(1 for w in witnesses if w.get("trust_state") not in ("healthy",))
                / max(total, 1)
            )
            confidence = round((majority_votes / total) * (1.0 - 0.3 * trust_penalty), 4)

        return DisagreementReport(
            has_disagreement=minority_votes > 0,
            agreeing_count=majority_votes,
            disagreeing_count=minority_votes,
            total_witnesses=total,
            quorum_policy=quorum_policy.name,
            quorum_met=quorum_met,
            confidence=confidence,
            byzantine_faults=len(byzantine),
            resolution_strategy=resolution_strategy.name,
            detail=detail,
            resolution_guidance=resolution_guidance,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _tally_claims(
        witnesses: list[dict[str, Any]],
        agent_proficiencies: dict[str, float] | None,
        quorum_policy: QuorumPolicy,
    ) -> dict[str, Any]:
        """Tally claim hashes and find the majority."""
        claim_counts: dict[str, int] = {}
        claim_weighted: dict[str, float] = {}

        for w in witnesses:
            ch = w.get("claim_hash", "")
            if not ch:
                continue
            claim_counts[ch] = claim_counts.get(ch, 0) + 1

            if agent_proficiencies and quorum_policy == QuorumPolicy.WEIGHTED_BY_PROFICIENCY:
                prof = agent_proficiencies.get(w.get("witness_id", ""), 0.5)
                claim_weighted[ch] = claim_weighted.get(ch, 0.0) + prof
            else:
                claim_weighted[ch] = claim_weighted.get(ch, 0.0) + 1.0

        if not claim_counts:
            return {
                "majority_claim": "",
                "majority_votes": 0,
                "weighted_agreement_ratio": 0.0,
            }

        if quorum_policy == QuorumPolicy.WEIGHTED_BY_PROFICIENCY and agent_proficiencies:
            majority_claim = max(claim_weighted, key=lambda k: claim_weighted[k])
            total_weight = sum(agent_proficiencies.get(w.get("witness_id", ""), 0.5)
                              for w in witnesses)
            weighted_ratio = (
                claim_weighted[majority_claim] / max(total_weight, 0.001)
            )
        else:
            majority_claim = max(claim_counts, key=lambda k: claim_counts[k])
            weighted_ratio = claim_counts[majority_claim] / max(len(witnesses), 1)

        return {
            "majority_claim": majority_claim,
            "majority_votes": claim_counts[majority_claim],
            "weighted_agreement_ratio": round(min(weighted_ratio, 1.0), 4),
        }

    @staticmethod
    def _detect_byzantine(
        witnesses: list[dict[str, Any]],
        majority_claim: str,
        total: int,
    ) -> list[str]:
        """Detect potentially Byzantine (faulty) witnesses.

        Byzantine tolerance: with 3f+1 total witnesses, can tolerate up to f
        faulty witnesses. Flags witnesses that disagree AND have degraded trust
        states as potentially Byzantine.
        """
        if total < 4:
            return []  # Need at least 4 for 3f+1 with f>=1

        max_byzantine = (total - 1) // 3  # f from 3f+1 ≤ total
        suspects: list[str] = []

        for w in witnesses:
            claim = w.get("claim_hash", "")
            trust = w.get("trust_state", "healthy")
            if claim != majority_claim and trust in ("restricted", "probation"):
                suspects.append(w.get("witness_id", "unknown"))

        return suspects[:max_byzantine]

    @staticmethod
    def _build_detail(
        witnesses: list[dict[str, Any]],
        majority_claim: str,
        agent_proficiencies: dict[str, float] | None,
    ) -> list[dict[str, Any]]:
        """Build per-witness detail records."""
        detail: list[dict[str, Any]] = []
        for w in witnesses:
            wid = w.get("witness_id", "unknown")
            claim = w.get("claim_hash", "")
            agrees = claim == majority_claim if majority_claim else True
            detail.append({
                "witness_id": wid,
                "agrees_with_majority": agrees,
                "claim_hash": claim[:16] + "..." if len(claim) > 16 else claim,
                "confidence": w.get("confidence", 0.0),
                "trust_state": w.get("trust_state", "unknown"),
                "proficiency": agent_proficiencies.get(wid) if agent_proficiencies else None,
            })
        return detail

    def _determine_strategy(
        self,
        *,
        quorum_met: bool,
        byzantine_count: int,
        total: int,
        quorum_policy: QuorumPolicy,
        agent_proficiencies: dict[str, float] | None,
        witnesses: list[dict[str, Any]],
    ) -> tuple[ResolutionStrategy, str]:
        """Determine the appropriate resolution strategy."""
        if quorum_met and byzantine_count == 0:
            return (
                ResolutionStrategy.MAJORITY_VOTE,
                "Quorum met with no Byzantine faults — majority claim accepted.",
            )

        if quorum_met and byzantine_count > 0:
            return (
                ResolutionStrategy.MAJORITY_VOTE,
                f"Quorum met with {byzantine_count} Byzantine suspect(s) — "
                "majority accepted, suspects flagged for review.",
            )

        if byzantine_count > 0:
            return (
                ResolutionStrategy.FLAG_FOR_OPERATOR,
                f"Quorum NOT met with {byzantine_count} Byzantine suspect(s) "
                f"out of {total} witnesses — operator review required.",
            )

        if not quorum_met and agent_proficiencies:
            return (
                ResolutionStrategy.DEFER_HIGHEST_PROFICIENCY,
                "Quorum not met — deferring to highest-proficiency witness.",
            )

        if not quorum_met:
            return (
                ResolutionStrategy.RERUN_WITH_MORE_GAS,
                "Quorum not met — recommend re-running with more witnesses "
                "or relaxed thresholds.",
            )

        return (
            ResolutionStrategy.FLAG_FOR_OPERATOR,
            "Unable to resolve automatically — flagging for operator review.",
        )


# ---------------------------------------------------------------------------
# Cross-Witness Prover
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CrossWitnessProof:
    """Result of a cross-witness agreement proof.

    Attributes:
        agreement_reached: Whether witnesses reached agreement.
        confidence: Aggregate confidence score (0.0 - 1.0).
        quorum_policy: The quorum policy used.
        quorum_satisfied: Whether the quorum threshold was met.
        total_witnesses: Number of witnesses evaluated.
        agreeing_witnesses: Count of witnesses supporting the consensus claim.
        disagreeing_witnesses: Count of witnesses opposing the consensus claim.
        consensus_claim_hash: The hash of the majority/consensus claim.
        byzantine_tolerance: Maximum Byzantine faults tolerated (f).
        byzantine_faults_detected: Actual Byzantine faults detected.
        proof_hash: Deterministic hash of the proof.
        resolution_report: The DisagreementReport if disagreement exists.
        generated_at: Unix timestamp of proof generation.
    """

    agreement_reached: bool
    confidence: float
    quorum_policy: str
    quorum_satisfied: bool
    total_witnesses: int
    agreeing_witnesses: int
    disagreeing_witnesses: int
    consensus_claim_hash: str
    byzantine_tolerance: int
    byzantine_faults_detected: int
    proof_hash: str
    resolution_report: dict[str, Any] | None = None
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agreement_reached": self.agreement_reached,
            "confidence": self.confidence,
            "quorum_policy": self.quorum_policy,
            "quorum_satisfied": self.quorum_satisfied,
            "total_witnesses": self.total_witnesses,
            "agreeing_witnesses": self.agreeing_witnesses,
            "disagreeing_witnesses": self.disagreeing_witnesses,
            "consensus_claim_hash": self.consensus_claim_hash,
            "byzantine_tolerance": self.byzantine_tolerance,
            "byzantine_faults_detected": self.byzantine_faults_detected,
            "proof_hash": self.proof_hash,
            "resolution_report": self.resolution_report,
            "generated_at": self.generated_at,
        }


class CrossWitnessProver:
    """Proves agreement or disagreement among N independent agents.

    Given N agents that independently produced knowledge claims, this
    prover determines consensus with confidence scores, handles Byzantine
    faults, and produces verifiable proof artifacts.
    """

    def __init__(
        self,
        quorum_policy: QuorumPolicy = QuorumPolicy.SIMPLE_MAJORITY,
    ) -> None:
        """Initialize the cross-witness prover.

        Args:
            quorum_policy: Default quorum policy for agreement verification.
        """
        self._quorum_policy = quorum_policy
        self._resolver = DisagreementResolver()

    def prove(
        self,
        witnesses: list[dict[str, Any]],
        quorum_policy: QuorumPolicy | None = None,
        agent_proficiencies: dict[str, float] | None = None,
    ) -> CrossWitnessProof:
        """Prove agreement across multiple witness claims.

        Args:
            witnesses: List of witness dicts with witness_id, claim_hash,
                confidence, and trust_state.
            quorum_policy: Override the default quorum policy.
            agent_proficiencies: Dict of agent_id → proficiency (0.0-1.0).

        Returns:
            CrossWitnessProof with complete agreement analysis.
        """
        policy = quorum_policy or self._quorum_policy

        if not witnesses:
            return CrossWitnessProof(
                agreement_reached=True,
                confidence=1.0,
                quorum_policy=policy.name,
                quorum_satisfied=True,
                total_witnesses=0,
                agreeing_witnesses=0,
                disagreeing_witnesses=0,
                consensus_claim_hash="",
                byzantine_tolerance=0,
                byzantine_faults_detected=0,
                proof_hash=self._compute_proof_hash({}),
            )

        total = len(witnesses)

        # Byzantine tolerance calculation: 3f+1 witnesses tolerate f faults
        max_f = (total - 1) // 3 if total >= 4 else 0

        # Tally claims
        claim_votes: dict[str, int] = {}
        claim_confidence: dict[str, list[float]] = {}
        for w in witnesses:
            ch = w.get("claim_hash", "")
            if not ch:
                continue
            claim_votes[ch] = claim_votes.get(ch, 0) + 1
            claim_confidence.setdefault(ch, []).append(
                float(w.get("confidence", 0.5))
            )

        if not claim_votes:
            return CrossWitnessProof(
                agreement_reached=False,
                confidence=0.0,
                quorum_policy=policy.name,
                quorum_satisfied=False,
                total_witnesses=total,
                agreeing_witnesses=0,
                disagreeing_witnesses=0,
                consensus_claim_hash="",
                byzantine_tolerance=max_f,
                byzantine_faults_detected=0,
                proof_hash=self._compute_proof_hash({}),
            )

        # Find consensus claim (weighted if policy is WEIGHTED_BY_PROFICIENCY)
        if policy == QuorumPolicy.WEIGHTED_BY_PROFICIENCY and agent_proficiencies:
            weighted: dict[str, float] = {}
            for w in witnesses:
                ch = w.get("claim_hash", "")
                wid = w.get("witness_id", "")
                prof = agent_proficiencies.get(wid, 0.5)
                weighted[ch] = weighted.get(ch, 0.0) + prof * float(w.get("confidence", 0.5))
            consensus_claim = max(weighted, key=lambda k: weighted[k])
            agreeing = sum(
                1 for w in witnesses
                if w.get("claim_hash") == consensus_claim
            )
        else:
            consensus_claim = max(claim_votes, key=lambda k: claim_votes[k])
            agreeing = claim_votes[consensus_claim]

        disagreeing = total - agreeing
        quorum_satisfied = agreeing >= policy.threshold(total)

        # Weighted-by-proficiency overrides quorum check: use weighted ratio
        if policy == QuorumPolicy.WEIGHTED_BY_PROFICIENCY and agent_proficiencies:
            total_weight = sum(
                agent_proficiencies.get(w.get("witness_id", ""), 0.5)
                * float(w.get("confidence", 0.5))
                for w in witnesses
            )
            consensus_weight = weighted.get(consensus_claim, 0.0)
            quorum_satisfied = (consensus_weight / max(total_weight, 0.001)) >= 0.5

        # Byzantine detection
        byzantine_count = 0
        if total >= 4:
            suspects = self._resolver._detect_byzantine(
                witnesses, consensus_claim, total
            )
            byzantine_count = min(len(suspects), max_f)

        # Compute aggregate confidence
        if quorum_satisfied:
            confidences = claim_confidence.get(consensus_claim, [0.5])
            avg_conf = sum(confidences) / len(confidences)
            # Penalize if Byzantine faults detected
            byz_penalty = 1.0 - 0.2 * (byzantine_count / max(total - agreeing, 1))
            confidence = round(avg_conf * min(byz_penalty, 1.0), 4)
        else:
            confidence = round(agreeing / max(total, 1), 4)

        agreement_reached = quorum_satisfied and byzantine_count <= max_f

        # Build resolution report if there's disagreement
        resolution_report: dict[str, Any] | None = None
        if disagreeing > 0 or not quorum_satisfied:
            report = self._resolver.resolve(witnesses, policy, agent_proficiencies)
            resolution_report = report.to_dict()

        proof_payload = {
            "total_witnesses": total,
            "agreeing_witnesses": agreeing,
            "disagreeing_witnesses": disagreeing,
            "quorum_policy": policy.name,
            "quorum_satisfied": quorum_satisfied,
            "consensus_claim_hash": consensus_claim,
            "byzantine_tolerance": max_f,
            "byzantine_faults_detected": byzantine_count,
            "agreement_reached": agreement_reached,
            "timestamp": time.time(),
        }

        return CrossWitnessProof(
            agreement_reached=agreement_reached,
            confidence=confidence,
            quorum_policy=policy.name,
            quorum_satisfied=quorum_satisfied,
            total_witnesses=total,
            agreeing_witnesses=agreeing,
            disagreeing_witnesses=disagreeing,
            consensus_claim_hash=consensus_claim,
            byzantine_tolerance=max_f,
            byzantine_faults_detected=byzantine_count,
            proof_hash=self._compute_proof_hash(proof_payload),
            resolution_report=resolution_report,
        )

    def prove_multi_claim(
        self,
        claims_by_witness: dict[str, list[str]],
        quorum_policy: QuorumPolicy | None = None,
    ) -> dict[str, CrossWitnessProof]:
        """Prove agreement across multiple independent knowledge claims.

        Each witness produces claims on potentially multiple knowledge items.
        This method groups by claim index and proves agreement per-claim.

        Args:
            claims_by_witness: Dict of witness_id → list of claim hashes (one per item).
            quorum_policy: Quorum policy override.

        Returns:
            Dict mapping claim index to CrossWitnessProof.
        """
        if not claims_by_witness:
            return {}

        # Determine max claims per witness
        max_claims = max(len(claims) for claims in claims_by_witness.values())
        proofs: dict[str, CrossWitnessProof] = {}

        for idx in range(max_claims):
            witnesses: list[dict[str, Any]] = []
            for wid, claims in claims_by_witness.items():
                if idx < len(claims):
                    witnesses.append({
                        "witness_id": wid,
                        "claim_hash": claims[idx],
                        "confidence": 0.8,
                        "trust_state": "healthy",
                    })

            proof = self.prove(witnesses, quorum_policy)
            proofs[f"claim_{idx}"] = proof

        return proofs

    def verify_proof(self, proof: CrossWitnessProof) -> bool:
        """Verify a cross-witness proof's integrity.

        Recomputes the proof hash and checks it matches.

        Args:
            proof: The CrossWitnessProof to verify.

        Returns:
            True if the proof is internally consistent.
        """
        expected_hash = self._compute_proof_hash({
            "total_witnesses": proof.total_witnesses,
            "agreeing_witnesses": proof.agreeing_witnesses,
            "disagreeing_witnesses": proof.disagreeing_witnesses,
            "quorum_policy": proof.quorum_policy,
            "quorum_satisfied": proof.quorum_satisfied,
            "consensus_claim_hash": proof.consensus_claim_hash,
            "byzantine_tolerance": proof.byzantine_tolerance,
            "byzantine_faults_detected": proof.byzantine_faults_detected,
            "agreement_reached": proof.agreement_reached,
            "timestamp": proof.generated_at,
        })
        return expected_hash == proof.proof_hash

    def aggregate_proofs(
        self,
        proofs: list[CrossWitnessProof],
    ) -> dict[str, Any]:
        """Aggregate multiple cross-witness proofs into a summary.

        Args:
            proofs: List of CrossWitnessProof instances.

        Returns:
            Aggregated summary dict.
        """
        if not proofs:
            return {
                "total_proofs": 0,
                "all_agreed": True,
                "average_confidence": 1.0,
                "total_byzantine_faults": 0,
                "quorum_issues": 0,
            }

        total = len(proofs)
        all_agreed = all(p.agreement_reached for p in proofs)
        avg_conf = sum(p.confidence for p in proofs) / total
        total_byz = sum(p.byzantine_faults_detected for p in proofs)
        quorum_issues = sum(1 for p in proofs if not p.quorum_satisfied)

        return {
            "total_proofs": total,
            "all_agreed": all_agreed,
            "average_confidence": round(avg_conf, 4),
            "total_byzantine_faults": total_byz,
            "quorum_issues": quorum_issues,
            "proofs": [p.to_dict() for p in proofs],
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_proof_hash(payload: dict[str, Any]) -> str:
        """Compute deterministic proof hash."""
        cleaned = {k: v for k, v in payload.items() if v is not None}
        return hashlib.sha256(
            json.dumps(cleaned, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
