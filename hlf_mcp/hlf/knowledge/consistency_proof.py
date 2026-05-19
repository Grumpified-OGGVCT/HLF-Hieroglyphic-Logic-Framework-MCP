"""ConsistencyProof — proves memory state is consistent across witnesses.

Aggregates witness testimony (TrustStateSnapshot), memory node state, and
entropy-anchor drift checks into a unified consistency proof.  Detects
divergent memory chains (forks) and validates cross-witness attestations.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from hlf_mcp.hlf.entropy_anchor import EntropyAnchorResult, evaluate_entropy_anchor
from hlf_mcp.hlf.witness_governance import (
    TrustStateSnapshot,
    WitnessObservation,
)


@dataclass(slots=True)
class ConsistencyProofResult:
    """Result of a consistency proof across witness snapshots and memory state.

    Attributes:
        consistent: Whether the memory state is consistent across witnesses.
        witness_count: Total number of witness snapshots considered.
        agreeing_witnesses: Number of witnesses whose testimony aligns.
        disagreeing_witnesses: Number of witnesses whose testimony conflicts.
        drift_detected: Whether entropy-anchor drift was detected on any node.
        proof_hash: Deterministic hash of the proof payload.
        rationale: Human-readable explanation of the consistency status.
        confidence: Aggregate confidence in the consistency (0.0 - 1.0).
    """

    consistent: bool
    witness_count: int
    agreeing_witnesses: int
    disagreeing_witnesses: int
    drift_detected: bool
    proof_hash: str
    rationale: str
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConsistencyProof:
    """Builds and verifies cross-witness consistency proofs.

    Aggregates witness governance snapshots, memory node state, and
    entropy-anchor drift checks into a unified proof structure.
    """

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_proof(
        self,
        witness_snapshots: list[TrustStateSnapshot],
        memory_nodes: list[dict[str, Any]],
        drift_results: list[EntropyAnchorResult],
    ) -> ConsistencyProofResult:
        """Build a consistency proof from witness snapshots, memory nodes, and drift results.

        Args:
            witness_snapshots: TrustStateSnapshot instances from witness governance.
            memory_nodes: Dict representations of memory nodes to check.
            drift_results: EntropyAnchorResult instances from drift checks.

        Returns:
            ConsistencyProofResult with aggregate consistency assessment.
        """
        witness_count = len(witness_snapshots)
        if witness_count == 0:
            return ConsistencyProofResult(
                consistent=True,
                witness_count=0,
                agreeing_witnesses=0,
                disagreeing_witnesses=0,
                drift_detected=False,
                proof_hash="",
                rationale="No witnesses to evaluate — consistency vacuously true.",
                confidence=1.0,
            )

        # Determine witness agreement by trust state alignment
        states = [ws.trust_state for ws in witness_snapshots]
        # Agreement: all healthy, or consistent degradation level
        healthy_count = states.count("healthy")
        restricted_count = states.count("restricted")
        probation_count = states.count("probation")
        watched_count = states.count("watched")

        # A witness is "agreeing" if its state matches the majority state
        # or if it's healthy (healthy always agrees)
        disagreeing_witnesses = 0
        for ws in witness_snapshots:
            # Disagreement criteria:
            #   - healthy agent when most are not healthy
            #   - agent in restricted when others are healthy
            if ws.trust_state == "healthy" and healthy_count <= witness_count // 2:
                disagreeing_witnesses += 1
            elif ws.trust_state in ("restricted", "probation") and healthy_count > witness_count // 2:
                disagreeing_witnesses += 1

        agreeing_witnesses = witness_count - disagreeing_witnesses

        # Evaluate drift across results
        drift_detected = any(r.drift_detected for r in drift_results)
        drift_count = sum(1 for r in drift_results if r.drift_detected)

        # Determine overall consistency
        consistent = True
        rationale_parts: list[str] = []

        if disagreeing_witnesses >= agreeing_witnesses and disagreeing_witnesses > 0:
            consistent = False
            rationale_parts.append(
                f"Majority of witnesses disagree: "
                f"{agreeing_witnesses} agree, {disagreeing_witnesses} disagree."
            )
        elif disagreeing_witnesses > 0:
            rationale_parts.append(
                f"Minor witness disagreement: "
                f"{disagreeing_witnesses}/{witness_count} disagree."
            )
        else:
            rationale_parts.append(
                f"All {witness_count} witnesses in agreement."
            )

        if drift_detected:
            consistent = False
            rationale_parts.append(
                f"Entropy-anchor drift detected on {drift_count} node(s)."
            )
        else:
            rationale_parts.append("No entropy-anchor drift detected.")

        # Compute confidence
        if consistent:
            confidence = 1.0
        else:
            # Confidence degrades with disagreement ratio and drift
            agreement_ratio = agreeing_witnesses / max(witness_count, 1)
            drift_penalty = drift_count / max(len(drift_results), 1) if drift_results else 0.0
            confidence = round(agreement_ratio * (1.0 - 0.5 * drift_penalty), 4)

        # Build deterministic proof hash
        proof_payload = {
            "witness_count": witness_count,
            "agreeing_witnesses": agreeing_witnesses,
            "disagreeing_witnesses": disagreeing_witnesses,
            "drift_detected": drift_detected,
            "consistent": consistent,
            "witness_states": sorted(states),
            "drift_count": drift_count,
            "memory_node_count": len(memory_nodes),
            "timestamp": time.time(),
        }
        proof_hash = hashlib.sha256(
            json.dumps(proof_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        return ConsistencyProofResult(
            consistent=consistent,
            witness_count=witness_count,
            agreeing_witnesses=agreeing_witnesses,
            disagreeing_witnesses=disagreeing_witnesses,
            drift_detected=drift_detected,
            proof_hash=proof_hash,
            rationale=" ".join(rationale_parts),
            confidence=confidence,
        )

    def verify_cross_witness(
        self,
        memory_hash: str,
        witnesses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Verify a memory entry is consistent across multiple witness attestations.

        Each witness dict is expected to contain at minimum an ``evidence_hash``
        field and may optionally contain ``category``, ``confidence``, and
        ``negative`` fields (as in WitnessObservation.to_dict()).

        Args:
            memory_hash: The SHA-256 content hash of the memory entry.
            witnesses: List of witness attestation dicts.

        Returns:
            Dict with ``consistent``, ``matching_count``, ``mismatching_count``,
            ``total``, and per-witness results.
        """
        if not witnesses:
            return {
                "consistent": True,
                "matching_count": 0,
                "mismatching_count": 0,
                "total": 0,
                "witness_results": [],
            }

        matching = 0
        mismatching = 0
        witness_results: list[dict[str, Any]] = []

        for witness in witnesses:
            evidence_hash = witness.get("evidence_hash", "")
            category = witness.get("category", "")
            witness_id = witness.get("witness_id", "unknown")
            negative = witness.get("negative", False)

            matches = evidence_hash == memory_hash if evidence_hash else None

            if matches is True:
                matching += 1
            elif matches is False:
                mismatching += 1
            # matches is None → cannot determine (no hash to compare)

            witness_results.append(
                {
                    "witness_id": witness_id,
                    "category": category,
                    "matches": matches,
                    "negative": negative,
                }
            )

        consistent = mismatching == 0 or matching > mismatching

        return {
            "consistent": consistent,
            "matching_count": matching,
            "mismatching_count": mismatching,
            "total": len(witnesses),
            "witness_results": witness_results,
        }

    def generate_consistency_report(
        self,
        proof: ConsistencyProofResult,
    ) -> dict[str, Any]:
        """Generate a structured report from a consistency proof.

        Args:
            proof: The ConsistencyProofResult to report on.

        Returns:
            Dict with a ``summary`` section and a ``details`` section.
        """
        return {
            "summary": {
                "consistent": proof.consistent,
                "confidence": proof.confidence,
                "witness_count": proof.witness_count,
                "agreement_ratio": (
                    proof.agreeing_witnesses / max(proof.witness_count, 1)
                ),
                "drift_detected": proof.drift_detected,
            },
            "details": {
                "agreeing_witnesses": proof.agreeing_witnesses,
                "disagreeing_witnesses": proof.disagreeing_witnesses,
                "proof_hash": proof.proof_hash,
                "rationale": proof.rationale,
            },
        }

    def detect_fork(
        self,
        chain_a: list[dict[str, Any]],
        chain_b: list[dict[str, Any]],
    ) -> bool:
        """Detect whether two memory chains have forked (diverged).

        Compares the merkle hashes of two chains node-by-node. A fork is
        detected when, after a shared common prefix, the hashes diverge.

        Each entry in the chains is a dict that must contain a ``merkle_hash``
        key (or ``content_hash`` as fallback).

        Args:
            chain_a: First memory chain (ordered list of node dicts).
            chain_b: Second memory chain (ordered list of node dicts).

        Returns:
            True if the chains have forked, False otherwise.
        """
        min_len = min(len(chain_a), len(chain_b))
        if min_len == 0:
            # One chain is empty; fork only if the other is non-empty
            return len(chain_a) != len(chain_b)

        for i in range(min_len):
            hash_a = chain_a[i].get("merkle_hash") or chain_a[i].get("content_hash", "")
            hash_b = chain_b[i].get("merkle_hash") or chain_b[i].get("content_hash", "")
            if hash_a != hash_b:
                return True

        # If chains have different lengths after common prefix, that's a fork
        return len(chain_a) != len(chain_b)
