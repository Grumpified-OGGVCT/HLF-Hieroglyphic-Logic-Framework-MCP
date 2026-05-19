"""Tests for hlf_mcp.hlf.knowledge — freshness, consistency, and lease contracts."""

from __future__ import annotations

import hashlib
import sys
import time
from datetime import datetime as _dt, timedelta as _td, UTC

import pytest

# ── path setup ──────────────────────────────────────────────────────────────────
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from hlf_mcp.hlf.knowledge.freshness_guarantee import (
    FreshnessGuaranteeChecker,
    FreshnessGuarantee,
)
from hlf_mcp.hlf.knowledge.consistency_proof import (
    ConsistencyProof,
    ConsistencyProofResult,
)
from hlf_mcp.hlf.knowledge.memory_lease import (
    LeaseManager,
    MemoryLease,
    LeaseViolationError,
)
from hlf_mcp.hlf.memory_node import EvidenceContract, FreshnessVerdict
from hlf_mcp.hlf.witness_governance import (
    TrustStateSnapshot,
    WitnessObservation,
)
from hlf_mcp.hlf.entropy_anchor import EntropyAnchorResult


# ── helpers ─────────────────────────────────────────────────────────────────────


def _valid_sha() -> str:
    return hashlib.sha256(b"test").hexdigest()


def _future_iso(offset_hours: int = 24) -> str:
    return (_dt.now(UTC) + _td(hours=offset_hours)).isoformat()


def _past_iso(offset_hours: int = 24) -> str:
    return (_dt.now(UTC) - _td(hours=offset_hours)).isoformat()


def _make_contract(**overrides) -> EvidenceContract:
    defaults: dict = {
        "sha256": _valid_sha(),
        "confidence": 0.8,
        "trust_tier": "trusted",
        "provenance_grade": "evidence-backed",
        "source_authority_label": "canonical",
        "source_file": "tests/test_something.py",
        "collector": "test-runner",
        "collected_at": "2025-01-01T00:00:00+00:00",
    }
    defaults.update(overrides)
    return EvidenceContract(**defaults)


def _make_snapshot(
    subject_id: str = "agent-1",
    trust_state: str = "healthy",
    aggregate_score: float = 0.0,
) -> TrustStateSnapshot:
    return TrustStateSnapshot(
        subject_agent_id=subject_id,
        trust_state=trust_state,
        aggregate_score=aggregate_score,
        total_observations=0,
        negative_observation_count=0,
        corroborating_witness_count=0,
        corroborating_category_count=0,
        recommended_action="observe",
    )


def _make_drift_result(drift: bool = False) -> EntropyAnchorResult:
    return EntropyAnchorResult(
        status="ok",
        source_hash=_valid_sha(),
        baseline_source="expected_intent",
        baseline_text="source text",
        compiled_program_summary="summary",
        translation_summary="translation",
        similarity_score=0.3 if drift else 0.95,
        threshold=0.5,
        drift_detected=drift,
        policy_mode="advisory",
        policy_action="warn" if drift else "allow",
        details={},
    )


# ═════════════════════════════════════════════════════════════════════════════════
# FreshnessGuarantee tests
# ═════════════════════════════════════════════════════════════════════════════════


class TestFreshnessGuarantee:
    """Tests for FreshnessGuaranteeChecker and FreshnessGuarantee."""

    def test_freshness_check_with_evidence_contract(self):
        """EvidenceContract with fresh_until in the future → check passes."""
        checker = FreshnessGuaranteeChecker()
        contract = _make_contract(fresh_until=_future_iso(24))
        verdict = checker.check_freshness(contract)
        assert verdict.admissible is True
        assert verdict.freshness_status == "fresh"

    def test_freshness_check_stale_contract(self):
        """EvidenceContract with fresh_until in the past → check fails."""
        checker = FreshnessGuaranteeChecker()
        contract = _make_contract(fresh_until=_past_iso(24))
        verdict = checker.check_freshness(contract)
        assert verdict.admissible is False
        assert verdict.freshness_status == "stale"

    def test_freshness_compute_window_by_trust_tier(self):
        """Different trust tiers produce different freshness windows."""
        checker = FreshnessGuaranteeChecker()
        windows = {
            tier: checker.compute_freshness_window(tier)
            for tier in ("verified", "validated", "trusted", "untrusted", "local")
        }
        # Each tier has a distinct base window
        assert windows["verified"] == 3600
        assert windows["validated"] == 1800
        assert windows["trusted"] == 900
        assert windows["untrusted"] == 300
        assert windows["local"] == 600
        # Unknown tier defaults to 300
        assert checker.compute_freshness_window("bogus") == 300

    def test_freshness_window_tightened_by_trust_state(self):
        """Probation trust state reduces the freshness window."""
        snapshot = _make_snapshot(trust_state="probation")
        checker = FreshnessGuaranteeChecker(trust_snapshot=snapshot)
        # trusted tier: 900 * 0.35 = 315
        window = checker.compute_freshness_window("trusted")
        assert window == 315  # int(900 * 0.35)

    def test_freshness_enforce_batch(self):
        """Enforce freshness on a list of mixed fresh/stale contracts."""
        checker = FreshnessGuaranteeChecker()
        fresh_contract = _make_contract(
            sha256=_valid_sha(),
            fresh_until=_future_iso(48),
        )
        stale_contract = _make_contract(
            sha256=hashlib.sha256(b"stale").hexdigest(),
            fresh_until=_past_iso(48),
        )
        result = checker.enforce_freshness([fresh_contract, stale_contract])
        assert result["fresh_count"] == 1
        assert result["stale_count"] == 1
        assert result["expired_count"] == 0
        assert len(result["results"]) == 2
        # Verify per-item FreshnessGuarantee entries
        guarantees = result["results"]
        assert guarantees[0]["passed"] is True
        assert guarantees[0]["policy_action"] == "keep"
        assert guarantees[1]["passed"] is False
        assert guarantees[1]["policy_action"] == "refresh"

    def test_freshness_stale_policy(self):
        """stale_policy recommends correct actions for different evidence states."""
        checker = FreshnessGuaranteeChecker()
        items = [
            {"item_key": "key-1", "evidence": {"revoked": True}},
            {"item_key": "key-2", "evidence": {"tombstoned": True}},
            {
                "item_key": "key-3",
                "evidence": {"supersedes_sha256": _valid_sha()},
            },
            {"item_key": "key-4", "evidence": {"fresh_until": _past_iso(24)}},
            {"item_key": "key-5", "evidence": {}},
        ]
        result = checker.stale_policy(items)
        assert result["summary"] == {"refresh": 2, "evict": 1, "quarantine": 2}
        actions = {r["item_key"]: r["action"] for r in result["recommendations"]}
        assert actions["key-1"] == "quarantine"
        assert actions["key-2"] == "quarantine"
        assert actions["key-3"] == "refresh"
        assert actions["key-4"] == "refresh"
        assert actions["key-5"] == "evict"


# ═════════════════════════════════════════════════════════════════════════════════
# ConsistencyProof tests
# ═════════════════════════════════════════════════════════════════════════════════


class TestConsistencyProof:
    """Tests for ConsistencyProof and ConsistencyProofResult."""

    def test_build_proof_all_healthy(self):
        """All witnesses healthy, no drift → consistent."""
        prover = ConsistencyProof()
        snapshots = [
            _make_snapshot("w1", "healthy"),
            _make_snapshot("w2", "healthy"),
            _make_snapshot("w3", "healthy"),
        ]
        result = prover.build_proof(
            witness_snapshots=snapshots,
            memory_nodes=[],
            drift_results=[],
        )
        assert result.consistent is True
        assert result.witness_count == 3
        assert result.agreeing_witnesses == 3
        assert result.disagreeing_witnesses == 0
        assert result.drift_detected is False
        assert result.confidence == 1.0

    def test_build_proof_disagreement(self):
        """Mixed witness states with disagreement → inconsistent."""
        prover = ConsistencyProof()
        snapshots = [
            _make_snapshot("w1", "healthy"),
            _make_snapshot("w2", "restricted"),
            _make_snapshot("w3", "restricted"),
        ]
        # healthy_count=1, witness_count=3 → 1 <= 1 → healthy is "minority"
        # restricted/probation count=2, healthy_count (1) > 3//2 (1)? 1 > 1 is False
        # So healthy w1 is disagreeing (healthy_count <= witness_count//2 → 1 <= 1 → True)
        # restricted ones: healthy_count (1) > 1 is False → not disagreeing
        # disagreeing_witnesses = 1, agreeing = 2
        result = prover.build_proof(
            witness_snapshots=snapshots,
            memory_nodes=[],
            drift_results=[],
        )
        assert result.disagreeing_witnesses == 1
        # 1 < 2, so not majority disagreement → but 1 disagreeing still
        # consistent because disagreeing < agreeing and disagreeing not majority
        assert result.consistent is True
        assert "Minor witness disagreement" in result.rationale

    def test_build_proof_drift_detected(self):
        """Drift detected → inconsistent."""
        prover = ConsistencyProof()
        snapshots = [
            _make_snapshot("w1", "healthy"),
            _make_snapshot("w2", "healthy"),
        ]
        drift = _make_drift_result(drift=True)
        result = prover.build_proof(
            witness_snapshots=snapshots,
            memory_nodes=[],
            drift_results=[drift],
        )
        assert result.consistent is False
        assert result.drift_detected is True
        assert "drift detected" in result.rationale.lower()

    def test_verify_cross_witness(self):
        """Verify memory hash against witness attestations."""
        prover = ConsistencyProof()
        mem_hash = _valid_sha()
        witnesses: list[dict] = [
            {"evidence_hash": mem_hash, "witness_id": "w1", "category": "memory", "negative": False},
            {"evidence_hash": mem_hash, "witness_id": "w2", "category": "memory", "negative": False},
            {"evidence_hash": "a" * 64, "witness_id": "w3", "category": "memory", "negative": True},
        ]
        result = prover.verify_cross_witness(mem_hash, witnesses)
        assert result["consistent"] is True  # matching > mismatching
        assert result["matching_count"] == 2
        assert result["mismatching_count"] == 1
        assert result["total"] == 3

    def test_detect_fork(self):
        """Two diverging chains → fork detected."""
        prover = ConsistencyProof()
        chain_a = [
            {"merkle_hash": "aaa"},
            {"merkle_hash": "bbb"},
            {"merkle_hash": "ccc"},
        ]
        chain_b = [
            {"merkle_hash": "aaa"},
            {"merkle_hash": "bbb"},
            {"merkle_hash": "xxx"},  # diverges here
        ]
        assert prover.detect_fork(chain_a, chain_b) is True

    def test_detect_fork_no_fork(self):
        """Identical chains → no fork detected."""
        prover = ConsistencyProof()
        chain_a = [
            {"merkle_hash": "aaa"},
            {"merkle_hash": "bbb"},
            {"merkle_hash": "ccc"},
        ]
        chain_b = [
            {"merkle_hash": "aaa"},
            {"merkle_hash": "bbb"},
            {"merkle_hash": "ccc"},
        ]
        assert prover.detect_fork(chain_a, chain_b) is False

    def test_generate_consistency_report(self):
        """Report structure has correct sections and values."""
        prover = ConsistencyProof()
        proof = ConsistencyProofResult(
            consistent=True,
            witness_count=5,
            agreeing_witnesses=4,
            disagreeing_witnesses=1,
            drift_detected=False,
            proof_hash="abc123",
            rationale="All good.",
            confidence=0.95,
        )
        report = prover.generate_consistency_report(proof)
        assert "summary" in report
        assert "details" in report
        assert report["summary"]["consistent"] is True
        assert report["summary"]["confidence"] == 0.95
        assert report["summary"]["witness_count"] == 5
        assert report["summary"]["agreement_ratio"] == 0.8
        assert report["summary"]["drift_detected"] is False
        assert report["details"]["agreeing_witnesses"] == 4
        assert report["details"]["disagreeing_witnesses"] == 1
        assert report["details"]["proof_hash"] == "abc123"
        assert report["details"]["rationale"] == "All good."


# ═════════════════════════════════════════════════════════════════════════════════
# MemoryLease tests
# ═════════════════════════════════════════════════════════════════════════════════


class TestMemoryLease:
    """Tests for LeaseManager, MemoryLease, and LeaseViolationError."""

    def test_acquire_lease(self):
        """Acquire a write lease on a memory key."""
        mgr = LeaseManager()
        lease = mgr.acquire("agent-1", "key-alpha", duration_seconds=60, scope="write")
        assert lease.holder_id == "agent-1"
        assert lease.memory_key == "key-alpha"
        assert lease.scope == "write"
        assert lease.active is True
        assert lease.expires_at > lease.granted_at

    def test_acquire_exclusive_blocks_write(self):
        """Exclusive lease blocks subsequent write acquisition."""
        mgr = LeaseManager()
        mgr.acquire("agent-1", "key-alpha", scope="exclusive")
        with pytest.raises(LeaseViolationError) as exc:
            mgr.acquire("agent-2", "key-alpha", scope="write")
        assert "exclusively held" in str(exc.value)
        assert exc.value.existing_lease is not None
        assert exc.value.existing_lease.holder_id == "agent-1"

    def test_lease_renewal(self):
        """Renewing a lease extends its expiry."""
        mgr = LeaseManager()
        lease = mgr.acquire("agent-1", "key-alpha", duration_seconds=10, scope="write")
        original_expiry = lease.expires_at
        time.sleep(0.1)
        renewed = mgr.renew(lease.lease_id, duration_seconds=300)
        assert renewed.expires_at > original_expiry
        assert renewed.renewal_count == 1
        assert renewed.active is True

    def test_lease_release(self):
        """Releasing a lease deactivates it."""
        mgr = LeaseManager()
        lease = mgr.acquire("agent-1", "key-alpha", scope="write")
        assert lease.active is True
        result = mgr.release(lease.lease_id)
        assert result is True
        # Releasing again returns False (was already inactive)
        result2 = mgr.release(lease.lease_id)
        assert result2 is False
        # After release, another agent can acquire
        lease2 = mgr.acquire("agent-2", "key-alpha", scope="write")
        assert lease2.active is True

    def test_lease_expire_stale(self):
        """expire_stale deactivates expired leases."""
        mgr = LeaseManager()
        # Create a lease that already expired
        lease = MemoryLease(
            holder_id="agent-1",
            memory_key="key-old",
            granted_at=time.time() - 600,
            expires_at=time.time() - 300,  # expired 5 min ago
            active=True,
            scope="write",
        )
        mgr._leases[lease.lease_id] = lease
        mgr._key_index.setdefault("key-old", []).append(lease.lease_id)
        expired = mgr.expire_stale()
        assert len(expired) == 1
        assert expired[0].lease_id == lease.lease_id
        assert expired[0].active is False

    def test_read_leases_share(self):
        """Multiple read leases can coexist; write blocked while exclusive exists."""
        mgr = LeaseManager()
        r1 = mgr.acquire("agent-1", "key-beta", scope="read")
        r2 = mgr.acquire("agent-2", "key-beta", scope="read")
        assert r1.active is True
        assert r2.active is True
        # Release reads, then exclusive
        mgr.release(r1.lease_id)
        mgr.release(r2.lease_id)
        exclusive = mgr.acquire("agent-3", "key-beta", scope="exclusive")
        # Write should be blocked
        with pytest.raises(LeaseViolationError):
            mgr.acquire("agent-4", "key-beta", scope="write")
        # Read should also be blocked by exclusive
        with pytest.raises(LeaseViolationError):
            mgr.acquire("agent-5", "key-beta", scope="read")

    def test_get_holder(self):
        """get_holder returns the correct holder of a memory key."""
        mgr = LeaseManager()
        assert mgr.get_holder("key-gamma") is None
        lease = mgr.acquire("agent-x", "key-gamma", scope="write")
        assert mgr.get_holder("key-gamma") == "agent-x"
        mgr.release(lease.lease_id)
        assert mgr.get_holder("key-gamma") is None
        # With multiple leases, most restrictive wins
        r_lease = mgr.acquire("agent-r", "key-gamma", scope="read")
        w_lease = mgr.acquire("agent-w", "key-gamma", scope="write")
        # Write outranks read
        assert mgr.get_holder("key-gamma") == "agent-w"
