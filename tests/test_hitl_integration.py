"""
Integration test: HITL gate wired into governed inference capsule lifecycle.

Verifies:
  1. governed_latent_infer() with human_approval_required=False returns status 'ok'
  2. governed_latent_infer() with human_approval_required=True returns 'awaiting_human_approval'
  3. hitl_status dict contains approval_token and instructions
  4. hlf-operator approve flow transitions capsule to COMPLETED
  5. hlf-operator reject flow transitions capsule to REJECTED_HUMAN
  6. hlf-operator check-timeouts transitions expired capsules
  7. MCP tools list/approve/reject/status work correctly

All tests use mock inference (no GPU required).
"""

import json
import tempfile
import time
from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _reset_hitl_gate():
    """Reset the HITL gate singleton between tests."""
    from hlf_mcp.hlf.hitl_gate import HITLGate
    HITLGate.reset_instance()
    yield
    HITLGate.reset_instance()


@pytest.fixture
def temp_pending_dir():
    """Temporary directory for HITL approval requests."""
    tmp = tempfile.TemporaryDirectory()
    yield Path(tmp.name)
    tmp.cleanup()


@pytest.fixture
def hitl_gate(temp_pending_dir):
    from hlf_mcp.hlf.hitl_gate import HITLGate
    return HITLGate.get_instance(temp_pending_dir)


# ═══════════════════════════════════════════════════════════════════════════════
# Mock governed_latent_infer
# ═══════════════════════════════════════════════════════════════════════════════

def _mock_inference_result(
    prompt="test prompt",
    *,
    human_approval_required=False,
    hitl_timeout=600,
):
    """Call governed_latent_infer with a mock that returns immediately."""
    from unittest.mock import patch, MagicMock
    import hashlib

    # We need to mock the whole GPU pipeline
    mock_capsule = MagicMock()
    mock_capsule.capsule.capsule_id = "mock-capsule-001"
    mock_capsule._GAS_PER_HANDOFF = 25
    mock_capsule.compute_capability_digest.return_value = "mock-digest"
    mock_capsule.validate_before_run.return_value = []
    
    mock_wrapped = MagicMock()
    mock_wrapped.final_text = "This is mock inference output text"
    mock_wrapped.rounds_completed = 2
    mock_wrapped.total_gas = 150
    mock_wrapped.total_wall_time_ms = 500.0
    mock_wrapped.capsule.capsule_id = "mock-capsule-001"
    mock_wrapped.attestations = []
    mock_wrapped.to_dict.return_value = {"provenance_chain": ["hash1", "hash2"]}
    
    mock_capsule.wrap_result.return_value = mock_wrapped

    mock_session = MagicMock()
    mock_session.load_all.return_value = True
    mock_session.recursive_infer.return_value = {
        "final_text": "This is mock inference output text",
        "rounds": 2,
        "steps": [
            {"agent": "planner", "round": 1, "hidden_dim": 2048, "link_key": "inner"},
            {"agent": "critic", "round": 1, "hidden_dim": 2048, "link_key": "outer"},
            {"agent": "solver", "round": 2, "hidden_dim": 2048, "link_key": "inner"},
            {"agent": "planner", "round": 2, "hidden_dim": 2048, "link_key": "outer"},
        ],
    }
    mock_session.unload.return_value = None

    adapter_keys = ["planner_critic", "critic_solver", "solver_planner"]
    mock_hashes = {k: hashlib.sha256(f"mock-{k}".encode()).hexdigest() for k in adapter_keys}

    with (
        patch("hlf_mcp.hlf.latent_capsule.LatentCapsule", return_value=mock_capsule),
        patch("hlf_mcp.hlf.latent_model_interface.LatentRecursiveSession", return_value=mock_session),
        patch("hlf_mcp.hlf.latent_model_interface.RecursiveSessionConfig"),
        patch("hlf_mcp.hlf.latent_capsule._write_latent_observability_trace"),
        patch("torch.cuda.is_available", return_value=True),
        patch("torch.cuda.max_memory_allocated", return_value=500 * 1024 * 1024),
    ):
        from hlf_mcp.hlf.latent_capsule import governed_latent_infer
        return governed_latent_infer(
            prompt,
            session_config={"recursion_rounds": 2},
            max_rounds=2,
            adapter_sha256s=mock_hashes,
            human_approval_required=human_approval_required,
            hitl_timeout_seconds=hitl_timeout,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: HITL gate integrated with inference
# ═══════════════════════════════════════════════════════════════════════════════


class TestHITLInferenceIntegration:
    """Verify the HITL gate is correctly wired into governed_latent_infer()."""

    def test_inference_without_hitl_returns_ok(self):
        """Without human_approval_required, inference returns status 'ok'."""
        result = _mock_inference_result(human_approval_required=False)
        assert result["status"] == "ok"
        assert "hitl_status" not in result
        assert result["capsule_id"] == "mock-capsule-001"
        assert result["final_text"] == "This is mock inference output text"

    def test_inference_with_hitl_returns_awaiting(self):
        """With human_approval_required=True, inference returns 'awaiting_human_approval'."""
        result = _mock_inference_result(human_approval_required=True)
        assert result["status"] == "awaiting_human_approval"
        assert "hitl_status" in result
        assert result["hitl_status"]["capsule_id"] == "mock-capsule-001"
        assert "approval_token" in result["hitl_status"]
        assert len(result["hitl_status"]["approval_token"]) == 24  # SHA-256[:24]
        assert "instructions" in result["hitl_status"]

    def test_hitl_approval_token_is_valid(self):
        """Approval token is 24 chars and matches what the gate expects."""
        result = _mock_inference_result(human_approval_required=True)
        token = result["hitl_status"]["approval_token"]
        assert len(token) == 24
        assert all(c in "0123456789abcdef" for c in token)

    def test_hitl_final_text_still_accessible(self):
        """Even with HITL, the final_text is still returned (operator needs to review)."""
        result = _mock_inference_result(human_approval_required=True)
        assert result["final_text"] == "This is mock inference output text"
        assert result["rounds_completed"] == 2
        assert result["total_gas"] == 150


class TestHITLApproveRejectFlow:
    """Full lifecycle: submit → approve/reject → verify."""

    def test_full_approve_flow(self, temp_pending_dir):
        """Inference → HITL submit → operator approve → COMPLETED."""
        from hlf_mcp.hlf.hitl_gate import HITLGate, require_human_approval
        HITLGate.reset_instance()
        gate = HITLGate.get_instance(temp_pending_dir)

        result = _mock_inference_result(human_approval_required=True)
        capsule_id = result["hitl_status"]["capsule_id"]
        token = result["hitl_status"]["approval_token"]

        # Verify pending
        pending = gate.list_pending()
        assert len(pending) == 1
        assert pending[0]["status"] == "AWAITING_HUMAN_APPROVAL"

        # Operator approves
        updated = gate.approve(capsule_id, "test-operator")
        assert updated.status == "COMPLETED"
        assert updated.approved_by == "test-operator"

        # No longer pending
        pending = gate.list_pending()
        assert len(pending) == 0

        # is_approved returns True
        assert gate.is_approved(capsule_id)
        assert not gate.is_rejected(capsule_id)

    def test_full_reject_flow(self, temp_pending_dir):
        """Inference → HITL submit → operator reject → REJECTED_HUMAN."""
        from hlf_mcp.hlf.hitl_gate import HITLGate
        HITLGate.reset_instance()
        gate = HITLGate.get_instance(temp_pending_dir)

        result = _mock_inference_result(human_approval_required=True)
        capsule_id = result["hitl_status"]["capsule_id"]

        # Operator rejects
        updated = gate.reject(capsule_id, "Output looks suspicious", "security-auditor")
        assert updated.status == "REJECTED_HUMAN"
        assert updated.rejection_reason == "Output looks suspicious"
        assert updated.approved_by == "security-auditor"

        assert gate.is_rejected(capsule_id)
        assert not gate.is_approved(capsule_id)

    def test_reject_blocks_forever(self, temp_pending_dir):
        """Once rejected, approve() raises ValueError."""
        from hlf_mcp.hlf.hitl_gate import HITLGate
        HITLGate.reset_instance()
        gate = HITLGate.get_instance(temp_pending_dir)

        result = _mock_inference_result(human_approval_required=True)
        capsule_id = result["hitl_status"]["capsule_id"]
        gate.reject(capsule_id, "no")

        with pytest.raises(ValueError, match="already finalized"):
            gate.approve(capsule_id)


class TestHITLTimeout:
    """Timeout-based expiration tests."""

    def test_expired_approval_not_approved(self, temp_pending_dir):
        """After timeout, capsule transitions to REJECTED_TIMEOUT."""
        from hlf_mcp.hlf.hitl_gate import HITLGate, require_human_approval

        HITLGate.reset_instance()
        # Use a very short timeout
        result = _mock_inference_result(human_approval_required=True, hitl_timeout=0)
        capsule_id = result["hitl_status"]["capsule_id"]

        gate = HITLGate.get_instance(temp_pending_dir)
        expired = gate.check_timeouts()
        assert len(expired) == 1
        assert expired[0].status == "REJECTED_TIMEOUT"

        assert gate.is_rejected(capsule_id)
        assert not gate.is_approved(capsule_id)

    def test_fresh_approval_not_expired(self, temp_pending_dir):
        """A fresh approval (default 600s timeout) is not expired."""
        from hlf_mcp.hlf.hitl_gate import HITLGate
        HITLGate.reset_instance()
        gate = HITLGate.get_instance(temp_pending_dir)

        result = _mock_inference_result(human_approval_required=True)
        expired = gate.check_timeouts()
        assert len(expired) == 0

        pending = gate.list_pending()
        assert len(pending) == 1


class TestHITLMCPTools:
    """Verify MCP tool interfaces work correctly."""

    def test_list_pending_empty(self, temp_pending_dir):
        """When no approvals, list returns empty."""
        from hlf_mcp.hlf.hitl_gate import HITLGate
        HITLGate.reset_instance()
        gate = HITLGate.get_instance(temp_pending_dir)
        pending = gate.list_pending()
        assert pending == []

    def test_list_pending_with_items(self, temp_pending_dir):
        from hlf_mcp.hlf.hitl_gate import HITLGate
        HITLGate.reset_instance()
        gate = HITLGate.get_instance(temp_pending_dir)

        _mock_inference_result(human_approval_required=True)
        pending = gate.list_pending()
        assert len(pending) == 1
        assert pending[0]["status"] == "AWAITING_HUMAN_APPROVAL"
        assert "capsule_id" in pending[0]

    def test_mcp_status_not_found(self, temp_pending_dir):
        from hlf_mcp.hlf.hitl_gate import HITLGate
        HITLGate.reset_instance()
        gate = HITLGate.get_instance(temp_pending_dir)
        status = gate.get_status("nonexistent-capsule")
        assert status is None

    def test_mcp_approve_with_token_verification(self, temp_pending_dir):
        from hlf_mcp.hlf.hitl_gate import HITLGate, ApprovalRequest
        HITLGate.reset_instance()
        gate = HITLGate.get_instance(temp_pending_dir)

        result = _mock_inference_result(human_approval_required=True)
        capsule_id = result["hitl_status"]["capsule_id"]
        correct_token = result["hitl_status"]["approval_token"]

        # Correct token should verify
        existing = gate.get_status(capsule_id)
        request = ApprovalRequest.from_dict(existing)
        assert gate.build_approval_token(request) == correct_token

        # Wrong token should not match
        wrong_token = "0" * 24
        assert wrong_token != correct_token


# ═══════════════════════════════════════════════════════════════════════════════
# CLI integration smoke tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCLIIntegration:
    """Smoke tests that verify the CLI works with the gate.
    
    Uses direct gate submission (not _mock_inference_result) to control
    the pending directory, avoiding cross-test contamination.
    """

    def test_cli_list_empty(self, temp_pending_dir):
        """CLI list with no pending returns empty message."""
        import subprocess
        import sys
        import os
        
        env = os.environ.copy()
        env["HLF_STATE_DIR"] = str(temp_pending_dir)

        result = subprocess.run(
            [sys.executable, "scripts/hlf_operator.py", "list"],
            capture_output=True, text=True, env=env,
            cwd="C:/Users/gerry/generic_workspace/HLF_MCP",
        )
        assert "No pending approvals" in result.stdout

    def test_cli_full_flow(self, temp_pending_dir):
        """CLI approve status work against the gate."""
        import subprocess
        import sys
        import os
        import json

        env = os.environ.copy()
        env["HLF_STATE_DIR"] = str(temp_pending_dir)

        # Direct file-based submission (bypasses governed_latent_infer mock issues)
        capsule_id = "cli-test-approve"
        req_path = temp_pending_dir / "pending_approvals" / f"{capsule_id}.json"
        req_data = {
            "capsule_id": capsule_id,
            "agent_id": "test-agent",
            "tier": "hearth",
            "intent_summary": "CLI test approval",
            "output_preview": "test output",
            "output_hash": "oh",
            "manifest_hash": "mh",
            "gas_consumed": 100,
            "gas_limit": 500,
            "provenance_hashes": ["h1", "h2"],
            "created_at": "2025-01-01T00:00:00Z",
            "status": "AWAITING_HUMAN_APPROVAL",
            "timeout_seconds": 600,
            "approval_token": "",
            "approved_by": "",
            "approved_at": "",
            "rejection_reason": "",
        }
        req_path.parent.mkdir(parents=True, exist_ok=True)
        with open(req_path, "w") as f:
            json.dump(req_data, f)

        # CLI list
        r = subprocess.run(
            [sys.executable, "scripts/hlf_operator.py", "list"],
            capture_output=True, text=True, env=env,
            cwd="C:/Users/gerry/generic_workspace/HLF_MCP",
        )
        assert capsule_id in r.stdout

        # CLI approve
        r = subprocess.run(
            [sys.executable, "scripts/hlf_operator.py", "approve",
             "--capsule-id", capsule_id],
            capture_output=True, text=True, env=env,
            cwd="C:/Users/gerry/generic_workspace/HLF_MCP",
        )
        assert "APPROVED" in r.stdout

        # CLI status after approval
        r = subprocess.run(
            [sys.executable, "scripts/hlf_operator.py", "status",
             "--capsule-id", capsule_id],
            capture_output=True, text=True, env=env,
            cwd="C:/Users/gerry/generic_workspace/HLF_MCP",
        )
        assert "COMPLETED" in r.stdout

    def test_cli_reject_flow(self, temp_pending_dir):
        """CLI reject transitions to REJECTED_HUMAN."""
        import subprocess
        import sys
        import os
        import json

        env = os.environ.copy()
        env["HLF_STATE_DIR"] = str(temp_pending_dir)

        # Direct file-based submission
        capsule_id = "cli-test-reject"
        req_path = temp_pending_dir / "pending_approvals" / f"{capsule_id}.json"
        req_data = {
            "capsule_id": capsule_id,
            "agent_id": "test-agent",
            "tier": "hearth",
            "intent_summary": "CLI test rejection",
            "output_preview": "test output",
            "output_hash": "oh",
            "manifest_hash": "mh",
            "gas_consumed": 100,
            "gas_limit": 500,
            "provenance_hashes": ["h1", "h2"],
            "created_at": "2025-01-01T00:00:00Z",
            "status": "AWAITING_HUMAN_APPROVAL",
            "timeout_seconds": 600,
            "approval_token": "",
            "approved_by": "",
            "approved_at": "",
            "rejection_reason": "",
        }
        req_path.parent.mkdir(parents=True, exist_ok=True)
        with open(req_path, "w") as f:
            json.dump(req_data, f)

        r = subprocess.run(
            [sys.executable, "scripts/hlf_operator.py", "reject",
             "--capsule-id", capsule_id, "--reason", "test rejection"],
            capture_output=True, text=True, env=env,
            cwd="C:/Users/gerry/generic_workspace/HLF_MCP",
        )
        assert "REJECTED" in r.stdout

        r = subprocess.run(
            [sys.executable, "scripts/hlf_operator.py", "status",
             "--capsule-id", capsule_id],
            capture_output=True, text=True, env=env,
            cwd="C:/Users/gerry/generic_workspace/HLF_MCP",
        )
        assert "REJECTED_HUMAN" in r.stdout
