"""Tests for HITL Gate — proves the gate blocks VERIFY→MERGE until human approval."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pytest

from hlf_mcp.hlf.hitl_gate import (
    HITLGate,
    ApprovalRequest,
    require_human_approval,
    DEFAULT_TIMEOUT_SECONDS,
)


@pytest.fixture(autouse=True)
def reset_gate():
    """Reset the HITLGate singleton before each test."""
    HITLGate.reset_instance()
    # Use a temp directory for tests
    import tempfile
    import shutil
    tmpdir = Path(tempfile.mkdtemp(prefix="hitl_test_"))
    gate = HITLGate.get_instance(tmpdir)
    yield gate
    # Ensure all files are closed before cleanup
    HITLGate.reset_instance()
    try:
        shutil.rmtree(str(tmpdir), ignore_errors=True)
    except PermissionError:
        pass  # Windows file locking — ignore cleanup failures


class TestApprovalRequest:
    """Unit tests for ApprovalRequest dataclass."""

    def test_create_request(self):
        req = ApprovalRequest(
            capsule_id="test-123",
            agent_id="medical-solver",
            tier="hearth",
            intent_summary="Diagnose hypothyroidism from lab results",
            output_preview="Diagnosis: subclinical hypothyroidism...",
            manifest_hash="abc123",
            output_hash="def456",
            gas_consumed=400,
            gas_limit=500,
        )
        assert req.capsule_id == "test-123"
        assert req.status == "AWAITING_HUMAN_APPROVAL"
        assert req.tier == "hearth"
        assert req.gas_consumed == 400

    def test_roundtrip_serialization(self):
        req = ApprovalRequest(
            capsule_id="roundtrip-test",
            agent_id="agent-1",
            tier="forge",
            intent_summary="extract structured data",
            output_preview="{'name': 'John'}",
            manifest_hash="mhash",
            output_hash="ohash",
            gas_consumed=100,
            gas_limit=500,
            provenance_hashes=["h1", "h2", "h3"],
        )
        d = req.to_dict()
        req2 = ApprovalRequest.from_dict(d)
        assert req2.capsule_id == req.capsule_id
        assert req2.status == req.status
        assert req2.provenance_hashes == ["h1", "h2", "h3"]

    def test_is_expired_fresh(self):
        req = ApprovalRequest(capsule_id="fresh", agent_id="a", tier="hearth",
                              intent_summary="x", output_preview="y",
                              manifest_hash="m", output_hash="o",
                              gas_consumed=0, gas_limit=100,
                              timeout_seconds=999999)
        assert not req.is_expired()

    def test_is_expired_stale(self):
        # Create with an old timestamp
        req = ApprovalRequest(capsule_id="stale", agent_id="a", tier="hearth",
                              intent_summary="x", output_preview="y",
                              manifest_hash="m", output_hash="o",
                              gas_consumed=0, gas_limit=100,
                              created_at="2020-01-01T00:00:00+00:00",
                              timeout_seconds=60)
        assert req.is_expired()


class TestHITLGate:
    """Tests for the HITLGate singleton and approval workflow."""

    def test_submit_and_approve(self, reset_gate):
        gate = reset_gate
        req = ApprovalRequest(
            capsule_id="capsule-alpha",
            agent_id="test-agent",
            tier="hearth",
            intent_summary="Test intent",
            output_preview="Test output preview",
            manifest_hash="mh-123",
            output_hash="oh-456",
            gas_consumed=150,
            gas_limit=500,
        )
        gate.submit_approval_request(req)

        # Should be pending
        status = gate.get_status("capsule-alpha")
        assert status is not None
        assert status["status"] == "AWAITING_HUMAN_APPROVAL"
        assert not gate.is_approved("capsule-alpha")

        # Approve
        gate.approve("capsule-alpha", "dr-smith")
        assert gate.is_approved("capsule-alpha")
        status = gate.get_status("capsule-alpha")
        assert status["status"] == "COMPLETED"
        assert status["approved_by"] == "dr-smith"

    def test_submit_and_reject(self, reset_gate):
        gate = reset_gate
        req = ApprovalRequest(
            capsule_id="capsule-beta",
            agent_id="test-agent",
            tier="hearth",
            intent_summary="Test",
            output_preview="Test",
            manifest_hash="mh",
            output_hash="oh",
            gas_consumed=50,
            gas_limit=100,
        )
        gate.submit_approval_request(req)

        gate.reject("capsule-beta", "diagnosis contradicts known patient history", "dr-jones")
        assert gate.is_rejected("capsule-beta")
        status = gate.get_status("capsule-beta")
        assert status["status"] == "REJECTED_HUMAN"
        assert "contradicts" in status["rejection_reason"]

    def test_list_pending(self, reset_gate):
        gate = reset_gate
        # Submit 3 requests
        for i in range(3):
            req = ApprovalRequest(
                capsule_id=f"capsule-{i}",
                agent_id="agent",
                tier="hearth",
                intent_summary=f"Intent {i}",
                output_preview=f"Output {i}",
                manifest_hash=f"mh-{i}",
                output_hash=f"oh-{i}",
                gas_consumed=i * 10,
                gas_limit=100,
            )
            gate.submit_approval_request(req)

        # Approve one
        gate.approve("capsule-1", "op")

        # Only 2 should be pending
        pending = gate.list_pending()
        assert len(pending) == 2
        pending_ids = [p["capsule_id"] for p in pending]
        assert "capsule-0" in pending_ids
        assert "capsule-2" in pending_ids
        assert "capsule-1" not in pending_ids  # approved

    def test_nonexistent_capsule(self, reset_gate):
        gate = reset_gate
        assert gate.get_status("nonexistent") is None
        assert not gate.is_approved("nonexistent")
        with pytest.raises(FileNotFoundError):
            gate.approve("nonexistent")

    def test_check_timeouts(self, reset_gate):
        gate = reset_gate
        # Submit with a very old timestamp
        req = ApprovalRequest(
            capsule_id="timed-out",
            agent_id="agent",
            tier="hearth",
            intent_summary="Old request",
            output_preview="Old output",
            manifest_hash="mh",
            output_hash="oh",
            gas_consumed=10,
            gas_limit=100,
            created_at="2020-01-01T00:00:00+00:00",
            timeout_seconds=60,
        )
        gate.submit_approval_request(req)

        expired = gate.check_timeouts()
        assert len(expired) == 1
        assert expired[0].capsule_id == "timed-out"
        assert expired[0].status == "REJECTED_TIMEOUT"
        assert gate.is_rejected("timed-out")

    def test_approval_token(self, reset_gate):
        gate = reset_gate
        req = ApprovalRequest(
            capsule_id="token-test",
            agent_id="agent",
            tier="hearth",
            intent_summary="Token test",
            output_preview="Token output",
            manifest_hash="mh",
            output_hash="oh",
            gas_consumed=10,
            gas_limit=100,
        )
        token = gate.build_approval_token(req)
        assert len(token) == 24  # SHA-256 truncated


class TestRequireHumanApproval:
    """Tests for the convenience function that submit approval from inference."""

    def test_require_human_approval_submits_request(self, reset_gate):
        gate = reset_gate
        req = require_human_approval(
            capsule_id="inference-capsule-1",
            agent_id="medical-solver",
            tier="hearth",
            intent_summary="Diagnose patient X",
            output_text="Patient has hypothyroidism. Recommend levothyroxine 25mcg.",
            manifest_hash="abc",
            output_hash="def",
            gas_consumed=300,
            gas_limit=500,
            provenance_hashes=["h1", "h2"],
        )

        assert req.status == "AWAITING_HUMAN_APPROVAL"
        assert req.capsule_id == "inference-capsule-1"

        # Should be on disk
        status = gate.get_status("inference-capsule-1")
        assert status is not None
        assert status["status"] == "AWAITING_HUMAN_APPROVAL"
        assert status["gas_consumed"] == 300
        assert len(status["provenance_hashes"]) == 2

    def test_require_then_approve_flow(self, reset_gate):
        """Full lifecycle: submit → pending → approve → COMPLETED."""
        gate = reset_gate

        # 1. Inference produces a result requiring human approval
        req = require_human_approval(
            capsule_id="full-flow-1",
            agent_id="pii-extractor",
            tier="sovereign",
            intent_summary="Extract PII from intake form, redact SSN",
            output_text="{'diagnosis': 'hypothyroidism', 'ssn': '[REDACTED]'}",
            manifest_hash="man-123",
            output_hash="out-456",
            gas_consumed=250,
            gas_limit=1000,
        )

        # 2. Operator checks status
        assert not gate.is_approved("full-flow-1")
        status = gate.get_status("full-flow-1")
        assert status["status"] == "AWAITING_HUMAN_APPROVAL"

        # 3. Operator approves
        gate.approve("full-flow-1", "compliance-officer")
        assert gate.is_approved("full-flow-1")

        # 4. Final status is COMPLETED
        final = gate.get_status("full-flow-1")
        assert final["status"] == "COMPLETED"
        assert final["approved_by"] == "compliance-officer"


class TestHITLBlocksMerge:
    """Integration-style tests proving the HITL gate blocks MERGE."""

    def test_capsule_stuck_at_verify_without_approval(self, reset_gate):
        """A capsule with human_approval_required should NOT be MERGEable
        until explicitly approved by an operator."""
        gate = reset_gate

        # Simulate what governed_latent_infer would do:
        # When human_approval_required=True, the inference result is sealed
        # but status is AWAITING_HUMAN_APPROVAL, not COMPLETED.
        req = require_human_approval(
            capsule_id="stuck-capsule",
            agent_id="pii-processor",
            tier="sovereign",
            intent_summary="Process PII-laden intake form",
            output_text="Diagnosis extracted. PII redacted.",
            manifest_hash="mh",
            output_hash="oh",
            gas_consumed=100,
            gas_limit=500,
        )

        # Before approval: NOT approved, NOT completed
        assert req.status == "AWAITING_HUMAN_APPROVAL"
        assert not gate.is_approved("stuck-capsule")

        # Simulate someone trying to MERGE without approval
        # The MERGE handler should check is_approved() first
        can_merge = gate.is_approved("stuck-capsule")
        assert not can_merge, "Capsule should NOT be mergeable without human approval!"

    def test_approve_then_merge(self, reset_gate):
        """After operator approval, the capsule CAN transition to COMPLETED/MERGE."""
        gate = reset_gate

        # Submit
        require_human_approval(
            capsule_id="approved-capsule",
            agent_id="agent",
            tier="hearth",
            intent_summary="Safe operation",
            output_text="All clear",
            manifest_hash="mh",
            output_hash="oh",
            gas_consumed=10,
            gas_limit=100,
        )

        # Not mergeable yet
        assert not gate.is_approved("approved-capsule")

        # Operator approves
        gate.approve("approved-capsule", "human-operator")

        # Now mergeable
        assert gate.is_approved("approved-capsule")
        status = gate.get_status("approved-capsule")
        assert status["status"] == "COMPLETED"

    def test_reject_blocks_merge_permanently(self, reset_gate):
        """Rejection should permanently block MERGE."""
        gate = reset_gate

        require_human_approval(
            capsule_id="rejected-capsule",
            agent_id="agent",
            tier="hearth",
            intent_summary="Suspicious operation",
            output_text="This looks wrong",
            manifest_hash="mh",
            output_hash="oh",
            gas_consumed=5,
            gas_limit=100,
        )

        gate.reject("rejected-capsule", "Output contains hallucinated diagnosis")

        assert gate.is_rejected("rejected-capsule")
        assert not gate.is_approved("rejected-capsule")

        # The MERGE handler should permanently refuse
        status = gate.get_status("rejected-capsule")
        assert status["status"] == "REJECTED_HUMAN"

    def test_timeout_blocks_merge(self, reset_gate):
        """An expired approval request should auto-reject and block MERGE."""
        gate = reset_gate

        # Submit with ancient timestamp
        req = ApprovalRequest(
            capsule_id="expired-capsule",
            agent_id="agent",
            tier="hearth",
            intent_summary="Old",
            output_preview="Old",
            manifest_hash="mh",
            output_hash="oh",
            gas_consumed=1,
            gas_limit=100,
            created_at="2020-01-01T00:00:00+00:00",
            timeout_seconds=60,
        )
        gate.submit_approval_request(req)

        expired = gate.check_timeouts()
        assert len(expired) == 1

        assert gate.is_rejected("expired-capsule")
        assert not gate.is_approved("expired-capsule")
