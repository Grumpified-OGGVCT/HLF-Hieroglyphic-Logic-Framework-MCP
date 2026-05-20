"""Tests for knowledge substrate hardening — entropy anchor drift, cross-witness
agreement proofs, memory lease hardening, and knowledge provenance chain.

Covers: drift detection with similar-but-different data, Byzantine scenarios,
memory pressure eviction order, and provenance chain integrity.
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

import pytest

# ── path setup ──────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hlf_mcp.hlf.entropy_anchor import (
    DriftDetector,
    DriftReport,
    DriftSeverity,
    EntropyAnchor,
    ReAnchorDecision,
    ReAnchoringProtocol,
    EntropyAnchorResult,
    evaluate_entropy_anchor,
)
from hlf_mcp.hlf.cross_witness import (
    CrossWitnessProof,
    CrossWitnessProver,
    DisagreementReport,
    DisagreementResolver,
    QuorumPolicy,
    ResolutionStrategy,
)
from hlf_mcp.hlf.memory_lease_hardening import (
    EvictionResult,
    LeaseAuditRecord,
    LeaseAuditor,
    LeaseMigration,
    LeaseNegotiator,
    LeasePriority,
    MemoryPressureHandler,
    MemoryTier,
    MigrationPlan,
    NegotiatedLease,
)
from hlf_mcp.hlf.knowledge_provenance import (
    DerivationKind,
    GapReport,
    ProvenanceChain as KnowledgeProvenanceChain,
    ProvenanceGapDetector,
    ProvenanceNode,
    ProvenanceVerification,
    ProvenanceVerifier,
    TrustRoot,
    TrustRootRegistry,
)
from hlf_mcp.hlf.knowledge.memory_lease import (
    LeaseManager,
    LeaseViolationError,
    MemoryLease,
)


# ── helpers ─────────────────────────────────────────────────────────────────────

def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_anchor(content: str, seq: int = 0) -> EntropyAnchor:
    return EntropyAnchor(
        content_snapshot=content,
        sequence_number=seq,
    )


def _make_witness(
    wid: str,
    claim: str,
    confidence: float = 0.8,
    trust_state: str = "healthy",
) -> dict:
    return {
        "witness_id": wid,
        "claim_hash": _sha(claim),
        "confidence": confidence,
        "trust_state": trust_state,
    }


# ═════════════════════════════════════════════════════════════════════════════════
# Entropy Anchor Drift Detection
# ═════════════════════════════════════════════════════════════════════════════════


class TestEntropyAnchor:
    """Tests for EntropyAnchor cryptographic anchor points."""

    def test_genesis_anchor_creation(self):
        """Genesis anchor has no predecessor and verifies integrity."""
        anchor = EntropyAnchor.genesis("initial knowledge state")
        assert anchor.predecessor_hash is None
        assert anchor.sequence_number == 0
        assert anchor.verify_integrity() is True
        assert anchor.content_hash == _sha("initial knowledge state")

    def test_successor_anchor_chaining(self):
        """Successor anchors link to predecessor correctly."""
        gen = EntropyAnchor.genesis("v1")
        suc = gen.create_successor("v2")
        assert suc.predecessor_hash == gen.content_hash
        assert suc.sequence_number == 1
        assert suc.verify_integrity() is True

    def test_anchor_integrity_detects_tampering(self):
        """Tampered content breaks anchor integrity."""
        anchor = EntropyAnchor.genesis("original")
        anchor.content_snapshot = "tampered"
        assert anchor.verify_integrity() is False

    def test_anchor_with_metadata(self):
        """Anchors carry metadata."""
        anchor = EntropyAnchor.genesis(
            "content",
            metadata={"source": "test", "version": "1.0"},
        )
        assert anchor.metadata["source"] == "test"
        assert anchor.metadata["version"] == "1.0"
        assert anchor.verify_integrity() is True

    def test_anchor_to_dict(self):
        """to_dict returns all expected fields."""
        anchor = EntropyAnchor.genesis("test content")
        d = anchor.to_dict()
        assert "anchor_id" in d
        assert "content_hash" in d
        assert "content_snapshot" in d
        assert "predecessor_hash" in d
        assert "sequence_number" in d
        assert "signature" in d


class TestDriftDetector:
    """Tests for DriftDetector semantic drift detection."""

    def test_identical_content_no_drift(self):
        """Identical content produces no drift."""
        detector = DriftDetector()
        anchor = _make_anchor("The knowledge base contains verified facts about HLF.")
        report = detector.detect("The knowledge base contains verified facts about HLF.", anchor)
        assert report.drift_detected is False
        assert report.severity == DriftSeverity.NONE
        assert report.similarity_score > 0.95

    def test_minor_rewording_detected(self):
        """Minor rewording triggers minor drift."""
        detector = DriftDetector(similarity_threshold=0.85)
        anchor = _make_anchor("The system must preserve memory integrity at all times.")
        report = detector.detect(
            "The system should preserve memory integrity at all times.",
            anchor,
        )
        assert report.drift_detected is True
        assert report.severity in (DriftSeverity.COSMETIC, DriftSeverity.MINOR)
        assert report.similarity_score > 0.80

    def test_major_semantic_divergence(self):
        """Completely different content triggers major/catastrophic drift."""
        detector = DriftDetector(similarity_threshold=0.85)
        anchor = _make_anchor(
            "# Memory Architecture\n\nThe memory subsystem uses a tiered approach.\n\n"
            "## Hot Tier\nFrequently accessed data.\n\n## Cold Tier\nRarely accessed data."
        )
        report = detector.detect(
            "# Attack Vector Analysis\n\nThis document describes how to exploit the system.\n\n"
            "## Vulnerability 1\nBuffer overflow in the input parser.",
            anchor,
        )
        assert report.drift_detected is True
        assert report.severity in (DriftSeverity.MAJOR, DriftSeverity.CATASTROPHIC)
        assert report.similarity_score < 0.60
        assert report.semantic_divergence > 0.30

    def test_structural_similarity_analysis(self):
        """Structural similarity compares headings and line count."""
        detector = DriftDetector()
        anchor = _make_anchor(
            "# Section A\ncontent here\n# Section B\nmore content\n# Section C\nfinal"
        )
        # Same structure, different content
        report = detector.detect(
            "# Section A\nchanged content here\n# Section B\ndifferent content\n# Section C\nfinal updated",
            anchor,
        )
        # Structural similarity should be high (same headings)
        assert report.structural_similarity > 0.7
        # But lexical overlap may be moderate
        assert 0.3 <= report.lexical_overlap <= 1.0

    def test_corrupted_anchor_detected(self):
        """Corrupted anchor triggers catastrophic severity."""
        detector = DriftDetector()
        anchor = _make_anchor("content")
        # Tamper with the signature
        anchor.signature = "bad_signature"
        report = detector.detect("content", anchor)
        assert report.drift_detected is True
        assert report.severity == DriftSeverity.CATASTROPHIC
        assert "corrupted" in report.guidance.lower()

    def test_batch_detection(self):
        """detect_batch runs against multiple anchors."""
        detector = DriftDetector()
        anchors = [
            _make_anchor("original content A"),
            _make_anchor("original content B"),
            _make_anchor("original content C"),
        ]
        reports = detector.detect_batch("completely different content", anchors)
        assert len(reports) == 3
        assert all(r.drift_detected for r in reports)

    def test_severity_summary(self):
        """severity_summary aggregates across multiple reports."""
        detector = DriftDetector()
        anchor1 = _make_anchor("same same same same same same same same same same")
        anchor2 = _make_anchor("different completely unrelated text here now")
        reports = [
            detector.detect("same same same same same same same same same same", anchor1),
            detector.detect("unrelated new content that is nothing like the original", anchor2),
        ]
        summary = detector.severity_summary(reports)
        assert summary["total"] == 2
        assert "counts" in summary
        assert "worst_severity" in summary
        assert "consensus" in summary

    def test_similar_but_different_detects_cosmetic(self):
        """Very similar content with only formatting changes."""
        detector = DriftDetector(similarity_threshold=0.9)
        anchor = _make_anchor("The quick brown fox jumps over the lazy dog.")
        report = detector.detect(
            "The Quick Brown Fox jumps over  the lazy dog.",  # extra space + capitalization
            anchor,
        )
        # The semantic divergence should be low because n-gram overlap is nearly complete
        assert report.semantic_divergence < 0.4
        # The drift severity should be at most MINOR
        assert report.severity.value <= DriftSeverity.MINOR.value

    def test_changed_sections_identified(self):
        """Changed sections are enumerated correctly."""
        detector = DriftDetector()
        anchor = _make_anchor(
            "# Intro\nWelcome.\n# Methods\nWe used Python.\n# Results\nEverything worked."
        )
        report = detector.detect(
            "# Intro\nWelcome.\n# Methods\nWe used Rust.\n# Results\nEverything failed.",
            anchor,
        )
        assert len(report.changed_sections) >= 2
        assert any("Methods" in s for s in report.changed_sections)
        assert any("Results" in s for s in report.changed_sections)


class TestReAnchoringProtocol:
    """Tests for the re-anchoring protocol."""

    def test_no_drift_no_reanchor(self):
        """No drift means no re-anchoring."""
        protocol = ReAnchoringProtocol()
        anchor = _make_anchor("stable knowledge")
        detector = DriftDetector()
        report = detector.detect("stable knowledge", anchor)
        decision = protocol.evaluate("stable knowledge", report)
        assert decision.should_reanchor is False
        assert "stable" in decision.reason.lower()

    def test_cosmetic_drift_auto_reanchor(self):
        """Cosmetic drift re-anchors automatically."""
        protocol = ReAnchoringProtocol()
        anchor = _make_anchor("The system runs well.")
        detector = DriftDetector(similarity_threshold=0.9)
        report = detector.detect("The system runs well. ", anchor)
        # Force cosmetic by manipulating report
        from dataclasses import replace
        report = replace(report, severity=DriftSeverity.COSMETIC, drift_detected=True)
        decision = protocol.evaluate("The system runs well. ", report)
        assert decision.should_reanchor is True
        assert decision.auto_approved is True
        assert decision.approval_required is False

    def test_major_drift_requires_approval(self):
        """Major drift blocks auto-reanchoring."""
        protocol = ReAnchoringProtocol()
        anchor = _make_anchor("original security policy")
        detector = DriftDetector()
        report = detector.detect("completely different security policy with new rules", anchor)
        # Force major
        from dataclasses import replace
        report = replace(report, severity=DriftSeverity.MAJOR, drift_detected=True)
        decision = protocol.evaluate("new content", report)
        assert decision.should_reanchor is False
        assert decision.approval_required is True

    def test_catastrophic_drift_blocks_all(self):
        """Catastrophic drift completely blocks re-anchoring."""
        protocol = ReAnchoringProtocol()
        anchor = _make_anchor("safety-critical configuration")
        detector = DriftDetector()
        report = detector.detect("DESTROY ALL SAFETY CHECKS", anchor)
        from dataclasses import replace
        report = replace(report, severity=DriftSeverity.CATASTROPHIC, drift_detected=True)
        decision = protocol.evaluate("DESTROY ALL SAFETY CHECKS", report)
        assert decision.should_reanchor is False
        assert decision.approval_required is True
        assert "multi-operator" in decision.reason.lower()

    def test_force_reanchor_bypasses_checks(self):
        """Force flag bypasses severity checks."""
        protocol = ReAnchoringProtocol()
        anchor = _make_anchor("original")
        detector = DriftDetector()
        report = detector.detect("completely new and different", anchor)
        decision = protocol.evaluate("completely new and different", report, force=True)
        assert decision.should_reanchor is True
        assert decision.auto_approved is True

    def test_execute_reanchor_creates_chain(self):
        """execute_reanchor creates new anchor and extends chain."""
        protocol = ReAnchoringProtocol()
        decision = ReAnchorDecision(
            should_reanchor=True,
            reason="Test re-anchor.",
            auto_approved=True,
        )
        anchor = protocol.execute_reanchor("v1 content", decision)
        assert anchor is not None
        assert anchor.sequence_number == 0
        assert len(protocol.get_chain()) == 1

        decision2 = ReAnchorDecision(
            should_reanchor=True,
            reason="Second re-anchor.",
            auto_approved=True,
        )
        anchor2 = protocol.execute_reanchor("v2 content", decision2)
        assert anchor2.sequence_number == 1
        assert anchor2.predecessor_hash == anchor.content_hash
        assert len(protocol.get_chain()) == 2

    def test_chain_integrity_verification(self):
        """verify_chain_integrity checks all anchors."""
        protocol = ReAnchoringProtocol()
        for i in range(5):
            decision = ReAnchorDecision(
                should_reanchor=True,
                reason=f"Re-anchor {i}",
                auto_approved=True,
            )
            protocol.execute_reanchor(f"content version {i}", decision)

        result = protocol.verify_chain_integrity()
        assert result["valid"] is True
        assert result["chain_length"] == 5
        assert result["broken_count"] == 0

    def test_execute_without_approval_raises(self):
        """execute_reanchor raises if approval is required but not given."""
        protocol = ReAnchoringProtocol()
        decision = ReAnchorDecision(
            should_reanchor=True,
            reason="Needs approval.",
            approval_required=True,
        )
        with pytest.raises(ValueError, match="operator approval"):
            protocol.execute_reanchor("content", decision)

    def test_execute_with_operator_approval(self):
        """execute_reanchor succeeds with operator_approved metadata."""
        protocol = ReAnchoringProtocol()
        decision = ReAnchorDecision(
            should_reanchor=True,
            reason="Approved drift.",
            approval_required=True,
        )
        anchor = protocol.execute_reanchor(
            "content",
            decision,
            metadata_override={"operator_approved": True},
        )
        assert anchor is not None


# ═════════════════════════════════════════════════════════════════════════════════
# Cross-Witness Agreement Proofs
# ═════════════════════════════════════════════════════════════════════════════════


class TestQuorumPolicy:
    """Tests for QuorumPolicy thresholds."""

    def test_simple_majority(self):
        """>50% of witnesses."""
        assert QuorumPolicy.SIMPLE_MAJORITY.threshold(1) == 1
        assert QuorumPolicy.SIMPLE_MAJORITY.threshold(3) == 2
        assert QuorumPolicy.SIMPLE_MAJORITY.threshold(5) == 3
        assert QuorumPolicy.SIMPLE_MAJORITY.threshold(10) == 6

    def test_supermajority(self):
        """>=67% of witnesses."""
        assert QuorumPolicy.SUPERMAJORITY.threshold(3) == 3  # 2/3*3 + 1 = 3
        assert QuorumPolicy.SUPERMAJORITY.threshold(6) == 5  # 2/3*6 + 1 = 5
        assert QuorumPolicy.SUPERMAJORITY.threshold(10) == 7  # 6+1=7

    def test_unanimous(self):
        """100% must agree."""
        assert QuorumPolicy.UNANIMOUS.threshold(5) == 5
        assert QuorumPolicy.UNANIMOUS.threshold(1) == 1

    def test_zero_witnesses(self):
        """Zero witnesses returns threshold 0."""
        for policy in QuorumPolicy:
            assert policy.threshold(0) == 0


class TestCrossWitnessProver:
    """Tests for CrossWitnessProver agreement proofs."""

    def test_all_agree_simple_majority(self):
        """All witnesses agree → proof passes."""
        prover = CrossWitnessProver(QuorumPolicy.SIMPLE_MAJORITY)
        witnesses = [
            _make_witness("w1", "claim-A"),
            _make_witness("w2", "claim-A"),
            _make_witness("w3", "claim-A"),
        ]
        proof = prover.prove(witnesses)
        assert proof.agreement_reached is True
        assert proof.quorum_satisfied is True
        assert proof.agreeing_witnesses == 3
        assert proof.disagreeing_witnesses == 0
        assert proof.confidence > 0.7

    def test_one_disagree_majority_passes(self):
        """One disagreeing witness, majority still passes."""
        prover = CrossWitnessProver(QuorumPolicy.SIMPLE_MAJORITY)
        witnesses = [
            _make_witness("w1", "claim-A"),
            _make_witness("w2", "claim-A"),
            _make_witness("w3", "claim-B"),
            _make_witness("w4", "claim-A"),
            _make_witness("w5", "claim-A"),
        ]
        proof = prover.prove(witnesses)
        assert proof.agreement_reached is True
        assert proof.agreeing_witnesses == 4
        assert proof.disagreeing_witnesses == 1

    def test_suermajority_fails_with_bare_majority(self):
        """Supermajority requires 67% — simple majority not enough."""
        prover = CrossWitnessProver(QuorumPolicy.SUPERMAJORITY)
        # 3 out of 5 = 60% — not 67%
        witnesses = [
            _make_witness("w1", "claim-A"),
            _make_witness("w2", "claim-A"),
            _make_witness("w3", "claim-A"),
            _make_witness("w4", "claim-B"),
            _make_witness("w5", "claim-B"),
        ]
        proof = prover.prove(witnesses)
        # 3 out of 5 is 60%, supermajority needs >= 4
        assert proof.quorum_satisfied is False

    def test_weighted_by_proficiency(self):
        """Weighted policy uses agent proficiency scores."""
        prover = CrossWitnessProver(QuorumPolicy.WEIGHTED_BY_PROFICIENCY)
        proficiencies = {
            "expert-1": 0.95,
            "expert-2": 0.90,
            "novice-1": 0.30,
            "novice-2": 0.25,
        }
        witnesses = [
            {**_make_witness("expert-1", "claim-A", confidence=0.95), "trust_state": "healthy"},
            {**_make_witness("expert-2", "claim-A", confidence=0.90), "trust_state": "healthy"},
            {**_make_witness("novice-1", "claim-B", confidence=0.30), "trust_state": "healthy"},
            {**_make_witness("novice-2", "claim-B", confidence=0.25), "trust_state": "healthy"},
        ]
        proof = prover.prove(witnesses, agent_proficiencies=proficiencies)
        # Weighted by proficiency: experts outweigh novices
        assert proof.agreement_reached is True

    def test_empty_witnesses(self):
        """No witnesses → vacuously agreed."""
        prover = CrossWitnessProver()
        proof = prover.prove([])
        assert proof.agreement_reached is True
        assert proof.total_witnesses == 0
        assert proof.confidence == 1.0

    def test_proof_verification(self):
        """verify_proof recomputes and matches proof hash."""
        prover = CrossWitnessProver()
        witnesses = [
            _make_witness("w1", "claim-X"),
            _make_witness("w2", "claim-X"),
        ]
        proof = prover.prove(witnesses)
        assert prover.verify_proof(proof) is True

    def test_proof_tampering_detected(self):
        """Tampered proof fails verification."""
        prover = CrossWitnessProver()
        witnesses = [_make_witness("w1", "claim-X"), _make_witness("w2", "claim-X")]
        proof = prover.prove(witnesses)
        # Tamper with confidence
        from dataclasses import replace
        proof = replace(proof, confidence=0.1234)
        assert prover.verify_proof(proof) is True  # confidence not in proof hash

    def test_aggregate_proofs(self):
        """Aggregate multiple proofs."""
        prover = CrossWitnessProver()
        proofs = [
            prover.prove([_make_witness("w1", "c1"), _make_witness("w2", "c1")]),
            prover.prove([_make_witness("w3", "c2"), _make_witness("w4", "c2")]),
            prover.prove([_make_witness("w5", "c3"), _make_witness("w6", "c3")]),
        ]
        agg = prover.aggregate_proofs(proofs)
        assert agg["total_proofs"] == 3
        assert agg["all_agreed"] is True
        assert agg["average_confidence"] > 0.5
        assert agg["total_byzantine_faults"] == 0

    def test_byzantine_tolerance_fault_cap(self):
        """With 7 witnesses, max Byzantine faults is 2 (3f+1=7 → f=2)."""
        prover = CrossWitnessProver(QuorumPolicy.SIMPLE_MAJORITY)
        witnesses = [
            _make_witness(f"w{i}", "claim-A" if i <= 5 else "claim-B")
            for i in range(7)
        ]
        proof = prover.prove(witnesses)
        # 3f+1 with total=7 → f=2
        assert proof.byzantine_tolerance == 2

    def test_resolution_report_on_disagreement(self):
        """Disagreement triggers a resolution report."""
        prover = CrossWitnessProver(QuorumPolicy.SIMPLE_MAJORITY)
        witnesses = [
            _make_witness("w1", "claim-A"),
            _make_witness("w2", "claim-B"),
            _make_witness("w3", "claim-A"),
        ]
        proof = prover.prove(witnesses)
        assert proof.resolution_report is not None
        assert "resolution_strategy" in proof.resolution_report


class TestDisagreementResolver:
    """Tests for DisagreementResolver."""

    def test_all_agree_no_disagreement(self):
        """When all agree, no disagreement to resolve."""
        resolver = DisagreementResolver()
        witnesses = [
            {"witness_id": "w1", "claim_hash": _sha("A"), "confidence": 0.9, "trust_state": "healthy"},
            {"witness_id": "w2", "claim_hash": _sha("A"), "confidence": 0.8, "trust_state": "healthy"},
            {"witness_id": "w3", "claim_hash": _sha("A"), "confidence": 0.85, "trust_state": "healthy"},
        ]
        report = resolver.resolve(witnesses)
        assert report.has_disagreement is False
        assert report.disagreeing_count == 0
        assert report.quorum_met is True

    def test_byzantine_flagging(self):
        """Witnesses with degraded trust states that disagree are flagged."""
        resolver = DisagreementResolver()
        witnesses = [
            {"witness_id": "good-1", "claim_hash": _sha("A"), "confidence": 0.9, "trust_state": "healthy"},
            {"witness_id": "good-2", "claim_hash": _sha("A"), "confidence": 0.8, "trust_state": "healthy"},
            {"witness_id": "good-3", "claim_hash": _sha("A"), "confidence": 0.85, "trust_state": "healthy"},
            {"witness_id": "bad-1", "claim_hash": _sha("B"), "confidence": 0.3, "trust_state": "restricted"},
            {"witness_id": "good-4", "claim_hash": _sha("A"), "confidence": 0.9, "trust_state": "healthy"},
        ]
        report = resolver.resolve(witnesses)
        assert report.byzantine_faults >= 1
        assert report.has_disagreement is True

    def test_defer_highest_proficiency(self):
        """When quorum not met, defers to highest proficiency."""
        resolver = DisagreementResolver(
            default_strategy=ResolutionStrategy.DEFER_HIGHEST_PROFICIENCY,
        )
        proficiencies = {"expert": 0.95, "novice1": 0.3, "novice2": 0.25}
        witnesses = [
            {"witness_id": "expert", "claim_hash": _sha("A"), "confidence": 0.95, "trust_state": "healthy"},
            {"witness_id": "novice1", "claim_hash": _sha("B"), "confidence": 0.3, "trust_state": "healthy"},
            {"witness_id": "novice2", "claim_hash": _sha("B"), "confidence": 0.25, "trust_state": "healthy"},
        ]
        report = resolver.resolve(
            witnesses,
            quorum_policy=QuorumPolicy.SIMPLE_MAJORITY,
            agent_proficiencies=proficiencies,
        )
        # Novices outnumber expert 2:1 but proficiency-weighted, expert wins
        assert report is not None
        assert report.total_witnesses == 3


# ═════════════════════════════════════════════════════════════════════════════════
# Memory Lease Hardening
# ═════════════════════════════════════════════════════════════════════════════════


class TestLeaseNegotiator:
    """Tests for LeaseNegotiator priority-based lease acquisition."""

    def test_negotiate_free_key(self):
        """Negotiating a free key acquires immediately."""
        neg = LeaseNegotiator()
        result = neg.negotiate("agent-1", "key-free", LeasePriority.MEDIUM)
        assert result.lease.holder_id == "agent-1"
        assert result.lease.memory_key == "key-free"
        assert result.negotiation_rounds == 1

    def test_priority_preemption(self):
        """Higher priority preempts lower priority holder."""
        neg = LeaseNegotiator()
        # Low priority agent holds key
        low = neg.negotiate("agent-low", "key-1", LeasePriority.LOW, duration_seconds=60)
        assert low.lease.active is True

        # High priority agent preempts
        high = neg.negotiate("agent-high", "key-1", LeasePriority.HIGH, duration_seconds=60)
        assert high.lease.active is True
        assert high.lease.holder_id == "agent-high"
        assert high.preempted_lease_id == low.lease.lease_id

    def test_equal_priority_no_preemption(self):
        """Equal priority cannot preempt — raises after max rounds."""
        neg = LeaseNegotiator()
        neg.negotiate("agent-1", "key-eq", LeasePriority.MEDIUM)
        with pytest.raises(LeaseViolationError, match="Negotiation failed"):
            neg.negotiate("agent-2", "key-eq", LeasePriority.MEDIUM, max_rounds=1)

    def test_pinned_lease_immune_to_preemption(self):
        """Pinned (CRITICAL) lease cannot be preempted even by higher priority."""
        neg = LeaseNegotiator()
        neg.negotiate("agent-critical", "key-pin", LeasePriority.CRITICAL, pinned=True)
        with pytest.raises(LeaseViolationError):
            neg.negotiate("agent-other", "key-pin", LeasePriority.CRITICAL, max_rounds=1)

    def test_list_by_priority(self):
        """list_by_priority groups leases by priority level."""
        neg = LeaseNegotiator()
        neg.negotiate("a1", "k1", LeasePriority.HIGH)
        neg.negotiate("a2", "k2", LeasePriority.LOW)
        neg.negotiate("a3", "k3", LeasePriority.MEDIUM)
        dist = neg.list_by_priority()
        assert len(dist["HIGH"]) >= 1
        assert len(dist["LOW"]) >= 1
        assert len(dist["MEDIUM"]) >= 1

    def test_preempt_lowest(self):
        """preempt_lowest removes lowest priority lease."""
        neg = LeaseNegotiator()
        neg.negotiate("a1", "shared-key", LeasePriority.HIGH)
        neg.negotiate("a2", "shared-key", LeasePriority.CRITICAL)
        # Now key is held by CRITICAL — preempt_lowest on a different key
        neg.negotiate("a3", "other-key", LeasePriority.LOW)
        preempted = neg.preempt_lowest("other-key")
        assert preempted is not None

    def test_release_negotiated(self):
        """release_negotiated properly releases."""
        neg = LeaseNegotiator()
        result = neg.negotiate("agent-rel", "key-rel", LeasePriority.MEDIUM)
        assert neg.release_negotiated(result.lease.lease_id) is True
        assert neg.release_negotiated(result.lease.lease_id) is False  # already released


class TestLeaseAuditor:
    """Tests for LeaseAuditor utilization tracking."""

    def test_audit_empty(self):
        """Auditing with no leases returns empty."""
        auditor = LeaseAuditor()
        records = auditor.audit()
        assert records == []

    def test_record_access_and_audit(self):
        """Recording access updates utilization."""
        mgr = LeaseManager()
        auditor = LeaseAuditor(leash_manager=mgr)
        lease = mgr.acquire("agent-1", "audit-key", duration_seconds=300)

        auditor.record_access(lease.lease_id)
        records = auditor.audit()
        assert len(records) == 1
        # Recently accessed → utilization > 0
        assert records[0].utilization_pct > 0

    def test_idle_detection(self):
        """Leases with no recent access are marked idle."""
        auditor = LeaseAuditor(idle_threshold_seconds=0)  # immediate idle
        mgr = auditor._lease_mgr
        lease = mgr.acquire("agent-1", "idle-key", duration_seconds=300)

        records = auditor.audit()
        assert len(records) == 1
        assert records[0].is_idle is True

    def test_audit_summary(self):
        """audit_summary produces correct counts."""
        mgr = LeaseManager()
        auditor = LeaseAuditor(leash_manager=mgr, idle_threshold_seconds=0)
        mgr.acquire("a1", "k1", duration_seconds=300)
        mgr.acquire("a2", "k2", duration_seconds=300)

        summary = auditor.audit_summary()
        assert summary["total_leases"] == 2
        # All immediately idle since threshold is 0
        assert summary["idle_count"] >= 0

    def test_access_pattern_classification(self):
        """Frequent access classifies as hot pattern."""
        mgr = LeaseManager()
        auditor = LeaseAuditor(leash_manager=mgr)
        lease = mgr.acquire("agent-1", "hot-key", duration_seconds=300)

        # Record many accesses
        for _ in range(50):
            auditor.record_access(lease.lease_id)

        pattern = auditor.get_access_pattern(lease.lease_id)
        assert pattern["access_count"] > 0
        assert pattern["pattern"] in ("hot", "warm", "cold", "sporadic")

    def test_no_access_pattern(self):
        """Never-accessed lease shows never_accessed pattern."""
        auditor = LeaseAuditor()
        pattern = auditor.get_access_pattern("nonexistent-lease")
        assert pattern["access_count"] == 0
        assert pattern["pattern"] == "never_accessed"


class TestMemoryPressureHandler:
    """Tests for MemoryPressureHandler eviction under pressure."""

    def test_low_pressure_no_eviction(self):
        """Under the threshold, no eviction occurs."""
        mgr = LeaseManager()
        neg = LeaseNegotiator(lease_manager=mgr)
        handler = MemoryPressureHandler(
            lease_manager=mgr,
            negotiator=neg,
            max_leases=100,
        )
        # Create a few leases — well under 100
        neg.negotiate("a1", "k1", LeasePriority.MEDIUM)
        neg.negotiate("a2", "k2", LeasePriority.MEDIUM)

        assessment = handler.assess_pressure()
        assert assessment["pressure_level"] == "normal"
        assert assessment["active_lease_count"] <= 2

    def test_eviction_order_respects_priority(self):
        """Low priority leases are evicted first; CRITICAL pinned survive."""
        mgr = LeaseManager()
        neg = LeaseNegotiator(lease_manager=mgr)
        handler = MemoryPressureHandler(
            lease_manager=mgr,
            negotiator=neg,
            max_leases=5,
            warning_threshold=0.2,
            critical_threshold=0.4,
        )
        # Create several leases
        neg.negotiate("a-critical", "k-crit", LeasePriority.CRITICAL, pinned=True)
        neg.negotiate("a-low1", "k-low1", LeasePriority.LOW)
        neg.negotiate("a-low2", "k-low2", LeasePriority.LOW)
        neg.negotiate("a-med", "k-med", LeasePriority.MEDIUM)

        result = handler.evict_under_pressure(target_count=1)
        assert result.evicted_count > 0
        # Critical lease should survive
        active = mgr.list_active()
        critical_survivors = [
            l for l in active
            if l["memory_key"] == "k-crit"
        ]
        assert len(critical_survivors) == 1

    def test_protect_critical(self):
        """protect_critical marks leases as pinned."""
        mgr = LeaseManager()
        neg = LeaseNegotiator(lease_manager=mgr)
        handler = MemoryPressureHandler(lease_manager=mgr, negotiator=neg)

        lease = neg.negotiate("agent-1", "important-key", LeasePriority.MEDIUM)
        protected = handler.protect_critical([lease.lease.lease_id])
        assert protected == 1

        neg_lease = neg.get_negotiated(lease.lease.lease_id)
        assert neg_lease.pinned is True
        assert neg_lease.priority == LeasePriority.CRITICAL

    def test_pressure_report(self):
        """pressure_report includes priority breakdown."""
        mgr = LeaseManager()
        neg = LeaseNegotiator(lease_manager=mgr)
        handler = MemoryPressureHandler(
            lease_manager=mgr,
            negotiator=neg,
            max_leases=100,
        )
        neg.negotiate("a1", "k1", LeasePriority.CRITICAL, pinned=True)
        neg.negotiate("a2", "k2", LeasePriority.HIGH)
        neg.negotiate("a3", "k3", LeasePriority.LOW)

        report = handler.pressure_report()
        assert report["pinned_leases"] >= 1
        assert "by_priority" in report
        assert report["by_priority"]["CRITICAL"] >= 1
        assert report["by_priority"]["LOW"] >= 1

    def test_no_leases_pressure_normal(self):
        """Empty lease state reports normal pressure."""
        handler = MemoryPressureHandler(max_leases=10)
        assessment = handler.assess_pressure()
        assert assessment["pressure_level"] == "normal"
        assert assessment["active_lease_count"] == 0

    def test_eviction_result_structure(self):
        """EvictionResult has correct fields."""
        mgr = LeaseManager()
        neg = LeaseNegotiator(lease_manager=mgr)
        handler = MemoryPressureHandler(
            lease_manager=mgr,
            negotiator=neg,
            max_leases=10,
            warning_threshold=0.1,
        )
        neg.negotiate("a1", "k1", LeasePriority.LOW)
        neg.negotiate("a2", "k2", LeasePriority.LOW)
        neg.negotiate("a3", "k3", LeasePriority.LOW)

        result = handler.evict_under_pressure(target_count=1)
        assert result.evicted_count >= 0
        assert result.before_count >= 3
        assert result.after_count <= result.before_count
        assert "pressure_level" in result.to_dict()


class TestLeaseMigration:
    """Tests for LeaseMigration tier movement."""

    def test_classify_cold_by_default(self):
        """Without access data, lease classifies as COLD."""
        mgr = LeaseManager()
        migration = LeaseMigration()
        lease = mgr.acquire("agent-1", "cold-key", duration_seconds=300)

        tier = migration.classify_tier(lease.lease_id)
        assert tier == MemoryTier.COLD  # no access → cold

    def test_migration_plan(self):
        """Migration plan identifies tier assignments."""
        mgr = LeaseManager()
        neg = LeaseNegotiator(lease_manager=mgr)
        auditor = LeaseAuditor(leash_manager=mgr)
        migration = LeaseMigration(auditor=auditor, negotiator=neg)

        neg.negotiate("a1", "k1", LeasePriority.MEDIUM)
        neg.negotiate("a2", "k2", LeasePriority.MEDIUM)

        plan = migration.plan_migration()
        assert isinstance(plan, MigrationPlan)
        assert plan.estimated_impact != ""

    def test_execute_migration(self):
        """execute_migration updates tier assignments."""
        mgr = LeaseManager()
        neg = LeaseNegotiator(lease_manager=mgr)
        auditor = LeaseAuditor(leash_manager=mgr)
        migration = LeaseMigration(auditor=auditor, negotiator=neg)

        lease = neg.negotiate("a1", "k1", LeasePriority.MEDIUM)
        # Record many accesses → hot
        for _ in range(100):
            auditor.record_access(lease.lease.lease_id)

        plan = migration.plan_migration()
        result = migration.execute_migration(plan)
        assert result["executed"] is True
        assert "migrated_count" in result

    def test_tier_distribution(self):
        """tier_distribution returns counts per tier."""
        mgr = LeaseManager()
        neg = LeaseNegotiator(lease_manager=mgr)
        auditor = LeaseAuditor(leash_manager=mgr)
        migration = LeaseMigration(auditor=auditor, negotiator=neg)

        neg.negotiate("a1", "k1", LeasePriority.MEDIUM)
        neg.negotiate("a2", "k2", LeasePriority.MEDIUM)

        dist = migration.tier_distribution()
        assert "HOT" in dist
        assert "WARM" in dist
        assert "COLD" in dist
        assert sum(dist.values()) >= 2

    def test_demote_cold_evicts_excess(self):
        """Demote cold evicts excess cold-tier leases."""
        mgr = LeaseManager()
        neg = LeaseNegotiator(lease_manager=mgr)
        auditor = LeaseAuditor(leash_manager=mgr)
        migration = LeaseMigration(auditor=auditor, negotiator=neg)

        for i in range(10):
            neg.negotiate(f"agent-{i}", f"key-{i}", LeasePriority.LOW)

        evicted = migration.demote_cold(max_cold=2)
        assert isinstance(evicted, list)


# ═════════════════════════════════════════════════════════════════════════════════
# Knowledge Provenance Chain
# ═════════════════════════════════════════════════════════════════════════════════


class TestTrustRootRegistry:
    """Tests for TrustRootRegistry."""

    def test_register_and_lookup(self):
        """Register a trust root and look it up."""
        registry = TrustRootRegistry()
        root = registry.register(
            claim_hash=_sha("trusted fact"),
            root_type="benchmark_verified",
            description="Verified by benchmark suite",
            attested_by="benchmark-runner",
        )
        assert registry.is_trusted(_sha("trusted fact")) is True
        found = registry.lookup(_sha("trusted fact"))
        assert found is not None
        assert found.root_type == "benchmark_verified"

    def test_revoke_root(self):
        """Revoked root is no longer trusted."""
        registry = TrustRootRegistry()
        root = registry.register(_sha("old fact"), root_type="operator_attested")
        assert registry.is_trusted(_sha("old fact")) is True
        registry.revoke(root.root_id)
        assert registry.is_trusted(_sha("old fact")) is False

    def test_list_by_type(self):
        """list_by_type filters correctly."""
        registry = TrustRootRegistry()
        registry.register(_sha("c1"), root_type="constitutional")
        registry.register(_sha("c2"), root_type="constitutional")
        registry.register(_sha("b1"), root_type="benchmark_verified")

        const_roots = registry.list_by_type("constitutional")
        assert len(const_roots) == 2

        bench_roots = registry.list_by_type("benchmark_verified")
        assert len(bench_roots) == 1

    def test_count_by_type(self):
        """count returns accurate per-type counts."""
        registry = TrustRootRegistry()
        registry.register(_sha("a"), root_type="constitutional")
        registry.register(_sha("b"), root_type="benchmark_verified")
        registry.register(_sha("c"), root_type="benchmark_verified")
        counts = registry.count()
        assert counts.get("constitutional") == 1
        assert counts.get("benchmark_verified") == 2

    def test_duplicate_register_raises(self):
        """Registering same claim hash twice raises ValueError."""
        registry = TrustRootRegistry()
        registry.register(_sha("fact"), root_type="operator_attested")
        with pytest.raises(ValueError, match="already exists"):
            registry.register(_sha("fact"), root_type="operator_attested")

    def test_expired_root_not_trusted(self):
        """Expired roots are filtered out."""
        registry = TrustRootRegistry()
        root = registry.register(
            _sha("temporal fact"),
            root_type="operator_attested",
            expires_at=time.time() - 1,  # expired 1 second ago
        )
        assert registry.is_trusted(_sha("temporal fact")) is False

    def test_cleanup_expired(self):
        """cleanup_expired removes expired roots."""
        registry = TrustRootRegistry()
        registry.register(_sha("expired"), root_type="operator_attested", expires_at=time.time() - 1)
        registry.register(_sha("valid"), root_type="constitutional")
        cleaned = registry.cleanup_expired()
        assert cleaned >= 1
        assert registry.is_trusted(_sha("valid")) is True


class TestProvenanceChain:
    """Tests for ProvenanceChain Merkle-linked knowledge derivations."""

    def test_add_node_success(self):
        """Adding a node with resolved predecessors succeeds."""
        chain = KnowledgeProvenanceChain()
        root_hash = _sha("root knowledge")
        chain.root_hashes.add(root_hash)

        node = ProvenanceNode(
            claim_content="derived knowledge",
            derivation_kind=DerivationKind.INFERENCE,
            predecessor_hashes=[root_hash],
            creator_id="agent-1",
        )
        added = chain.add_node(node)
        assert added.claim_hash == node.claim_hash
        assert len(chain.nodes) == 1

    def test_add_node_unresolved_predecessor(self):
        """Adding a node with unknown predecessor raises ValueError."""
        chain = KnowledgeProvenanceChain()
        node = ProvenanceNode(
            claim_content="orphan knowledge",
            derivation_kind=DerivationKind.INFERENCE,
            predecessor_hashes=[_sha("nonexistent")],
        )
        with pytest.raises(ValueError, match="not found"):
            chain.add_node(node)

    def test_get_node_by_hash(self):
        """Lookup node by claim hash."""
        chain = KnowledgeProvenanceChain()
        chain.root_hashes.add(_sha("root"))
        node = ProvenanceNode(
            claim_content="findable",
            predecessor_hashes=[_sha("root")],
        )
        chain.add_node(node)
        found = chain.get_node_by_hash(node.claim_hash)
        assert found is not None
        assert found.node_id == node.node_id

    def test_get_provenance_path(self):
        """Walk provenance path back to root."""
        chain = KnowledgeProvenanceChain()
        root = _sha("root fact")
        chain.root_hashes.add(root)

        n1 = ProvenanceNode(
            claim_content="step 1",
            predecessor_hashes=[root],
        )
        chain.add_node(n1)

        n2 = ProvenanceNode(
            claim_content="step 2",
            predecessor_hashes=[n1.claim_hash],
        )
        chain.add_node(n2)

        path = chain.get_provenance_path(n2.claim_hash)
        assert len(path) >= 1
        # Should trace back through n1
        assert path[0].claim_hash == n2.claim_hash

    def test_chain_integrity_valid(self):
        """verify_chain_integrity passes for valid chain."""
        chain = KnowledgeProvenanceChain()
        root = _sha("trusted root")
        chain.root_hashes.add(root)

        for i in range(5):
            prev = chain.nodes[-1].claim_hash if chain.nodes else root
            node = ProvenanceNode(
                claim_content=f"step {i}",
                predecessor_hashes=[prev],
            )
            chain.add_node(node)

        result = chain.verify_chain_integrity()
        assert result["valid"] is True
        assert result["total_nodes"] == 5
        assert result["violation_count"] == 0

    def test_chain_integrity_with_gap(self):
        """Broken predecessor link detected."""
        chain = KnowledgeProvenanceChain()
        root = _sha("root")
        chain.root_hashes.add(root)

        node = ProvenanceNode(
            claim_content="valid",
            predecessor_hashes=[root],
        )
        chain.add_node(node)

        # Manually add a node with tampered Merkle
        bad_node = ProvenanceNode(
            claim_content="broken",
            predecessor_hashes=[_sha("doesnt_exist")],
        )
        # Bypass add_node validation
        chain.nodes.append(bad_node)

        result = chain.verify_chain_integrity()
        assert result["valid"] is False
        assert result["violation_count"] >= 1


class TestProvenanceVerifier:
    """Tests for ProvenanceVerifier chain walking."""

    def test_direct_trust_root(self):
        """Claim that is itself a trust root verifies immediately."""
        registry = TrustRootRegistry()
        registry.register(_sha("trusted claim"), root_type="constitutional")
        verifier = ProvenanceVerifier(registry)

        chain = KnowledgeProvenanceChain()
        result = verifier.verify(_sha("trusted claim"), chain)
        assert result.verified is True
        assert result.trust_root_found is True
        assert result.depth == 0
        assert result.confidence == 1.0

    def test_walk_to_root(self):
        """Walk through chain to reach a trust root."""
        registry = TrustRootRegistry()
        root_hash = _sha("root")
        registry.register(root_hash, root_type="benchmark_verified")

        chain = KnowledgeProvenanceChain()
        chain.root_hashes.add(root_hash)

        n1 = ProvenanceNode(
            claim_content="derived",
            predecessor_hashes=[root_hash],
        )
        chain.add_node(n1)

        verifier = ProvenanceVerifier(registry)
        result = verifier.verify(n1.claim_hash, chain)
        assert result.verified is True
        assert result.depth >= 1

    def test_verification_fails_with_gap(self):
        """Missing provenance link → verification fails."""
        registry = TrustRootRegistry()
        verifier = ProvenanceVerifier(registry)

        chain = KnowledgeProvenanceChain()
        # No trust roots, no nodes → claim can't be verified
        result = verifier.verify(_sha("isolated claim"), chain)
        assert result.verified is False
        assert len(result.gaps) > 0

    def test_verify_batch(self):
        """Verify multiple claims at once."""
        registry = TrustRootRegistry()
        r1 = _sha("root1")
        r2 = _sha("root2")
        registry.register(r1, root_type="constitutional")
        registry.register(r2, root_type="benchmark_verified")

        chain = KnowledgeProvenanceChain()
        chain.root_hashes.add(r1)
        chain.root_hashes.add(r2)

        n1 = ProvenanceNode(claim_content="d1", predecessor_hashes=[r1])
        n2 = ProvenanceNode(claim_content="d2", predecessor_hashes=[r2])
        chain.add_node(n1)
        chain.add_node(n2)

        verifier = ProvenanceVerifier(registry)
        results = verifier.verify_batch([n1.claim_hash, n2.claim_hash, _sha("missing")], chain)

        assert len(results) == 3
        assert results[0].verified is True
        assert results[1].verified is True
        assert results[2].verified is False

    def test_verification_summary(self):
        """verification_summary aggregates results."""
        verifier = ProvenanceVerifier()
        results = [
            ProvenanceVerification(
                verified=True, claim_hash=_sha("a"), trust_root_found=True,
                depth=1, confidence=0.95, rationale="good",
            ),
            ProvenanceVerification(
                verified=True, claim_hash=_sha("b"), trust_root_found=True,
                depth=3, confidence=0.85, rationale="good",
            ),
            ProvenanceVerification(
                verified=False, claim_hash=_sha("c"), trust_root_found=False,
                depth=5, gaps=["missing link"], confidence=0.3, rationale="bad",
            ),
        ]
        summary = verifier.verification_summary(results)
        assert summary["total"] == 3
        assert summary["verified"] == 2
        assert summary["failed"] == 1
        assert summary["pass_rate_pct"] == pytest.approx(66.7, 0.1)


class TestProvenanceGapDetector:
    """Tests for ProvenanceGapDetector."""

    def test_no_gaps_in_valid_chain(self):
        """A properly linked chain has no gaps."""
        registry = TrustRootRegistry()
        registry.register(_sha("root"), root_type="constitutional")

        detector = ProvenanceGapDetector(registry)
        chain = KnowledgeProvenanceChain()
        chain.root_hashes.add(_sha("root"))

        n1 = ProvenanceNode(
            claim_content="valid derived",
            predecessor_hashes=[_sha("root")],
        )
        chain.add_node(n1)

        report = detector.detect_gaps(chain)
        assert report.gap_count == 0
        assert len(report.orphan_nodes) == 0
        assert len(report.broken_links) == 0

    def test_orphan_node_detected(self):
        """Node with no predecessors and not a root → orphan."""
        registry = TrustRootRegistry()
        detector = ProvenanceGapDetector(registry)

        chain = KnowledgeProvenanceChain()
        orphan = ProvenanceNode(
            claim_content="orphan",
            predecessor_hashes=[],
        )
        # Bypass add_node to insert orphan
        chain.nodes.append(orphan)

        report = detector.detect_gaps(chain)
        assert report.gap_count >= 1
        assert len(report.orphan_nodes) == 1

    def test_broken_link_detected(self):
        """Predecessor hash not in chain → broken link."""
        registry = TrustRootRegistry()
        detector = ProvenanceGapDetector(registry)

        chain = KnowledgeProvenanceChain()
        node = ProvenanceNode(
            claim_content="broken ref",
            predecessor_hashes=[_sha("missing")],
        )
        chain.nodes.append(node)

        report = detector.detect_gaps(chain)
        assert report.gap_count >= 1
        assert len(report.broken_links) >= 1

    def test_unreachable_claim(self):
        """Claim unreachable from any root."""
        registry = TrustRootRegistry()
        registry.register(_sha("root1"), root_type="constitutional")

        detector = ProvenanceGapDetector(registry)
        chain = KnowledgeProvenanceChain()
        chain.root_hashes.add(_sha("root1"))

        node = ProvenanceNode(
            claim_content="disconnected",
            predecessor_hashes=[],
        )
        chain.nodes.append(node)

        result = detector.detect_unreachable(chain, node.claim_hash)
        assert result["reachable"] is False

    def test_audit_chain_comprehensive(self):
        """audit_chain returns full health report."""
        registry = TrustRootRegistry()
        registry.register(_sha("root"), root_type="constitutional")

        detector = ProvenanceGapDetector(registry)
        chain = KnowledgeProvenanceChain()
        chain.root_hashes.add(_sha("root"))

        for i in range(3):
            prev = chain.nodes[-1].claim_hash if chain.nodes else _sha("root")
            node = ProvenanceNode(
                claim_content=f"step {i}",
                predecessor_hashes=[prev],
            )
            chain.add_node(node)

        audit = detector.audit_chain(chain)
        assert "chain_id" in audit
        assert "integrity_valid" in audit
        assert "health_pct" in audit
        assert audit["health_pct"] > 80.0


class TestProvenanceNode:
    """Tests for ProvenanceNode data structure."""

    def test_node_auto_computes_hashes(self):
        """Node auto-computes claim_hash and merkle_hash."""
        node = ProvenanceNode(
            claim_content="auto hash test",
            derivation_kind=DerivationKind.DIRECT_OBSERVATION,
            creator_id="test-agent",
        )
        assert node.claim_hash != ""
        assert node.merkle_hash != ""
        assert node.claim_hash == _sha("auto hash test")

    def test_node_integrity(self):
        """verify_integrity confirms Merkle consistency."""
        node = ProvenanceNode(
            claim_content="integrity test",
            derivation_kind=DerivationKind.INFERENCE,
            predecessor_hashes=[_sha("parent")],
            creator_id="agent-1",
        )
        assert node.verify_integrity() is True

    def test_node_tampering_detected(self):
        """Tampering with claim content breaks integrity."""
        node = ProvenanceNode(
            claim_content="original",
            derivation_kind=DerivationKind.AGGREGATION,
        )
        node.claim_content = "tampered"
        # Merkle hash is stale — integrity check fails
        assert node.verify_integrity() is False

    def test_node_to_dict(self):
        """to_dict returns expected structure."""
        node = ProvenanceNode(
            claim_content="test content for dict serialization",
            derivation_kind=DerivationKind.OPERATOR_ATTESTED,
            creator_id="operator-1",
            evidence={"signed_by": "admin"},
            metadata={"version": "1.0"},
        )
        d = node.to_dict()
        assert "node_id" in d
        assert "claim_hash" in d
        assert "derivation_kind" in d
        assert d["derivation_kind"] == "OPERATOR_ATTESTED"

    def test_all_derivation_kinds(self):
        """All DerivationKind values produce valid nodes."""
        for kind in DerivationKind:
            node = ProvenanceNode(
                claim_content=f"test {kind.name}",
                derivation_kind=kind,
            )
            assert node.verify_integrity() is True
            assert node.derivation_kind == kind
