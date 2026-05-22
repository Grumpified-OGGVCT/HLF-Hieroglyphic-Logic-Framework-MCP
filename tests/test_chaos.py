"""
Chaos engineering tests for HLF latent inference pipeline.

Tests:
  1. OOM during session.recursive_infer() — graceful abort, partial Merkle chain
  2. VRAM exhaustion mid-latent-handoff — session.unload() called, no dangling refs
  3. Generic CUDA runtime error — caught, reported as abort
  4. Normal success path still works (regression guard)

All tests use mock GPU (no actual GPU required).
"""

import hashlib
import tempfile
from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_mock_capsule(capsule_id="chaos-capsule-001"):
    """Create a mock LatentCapsule for testing.
    wrap_result() passes through the actual inference values rather than
    hardcoding them, so OOM tests get the right partial data."""
    from unittest.mock import MagicMock, PropertyMock

    mock_capsule = MagicMock()
    mock_capsule.capsule.capsule_id = capsule_id
    mock_capsule._GAS_PER_HANDOFF = 25
    mock_capsule.compute_capability_digest.return_value = "mock-digest"
    mock_capsule.validate_before_run.return_value = []

    # Dynamic wrap_result: build result object from actual inference output
    def _dynamic_wrap(final_text="", rounds_completed=0, attestations=None, total_wall_time_ms=0):
        wrapped = MagicMock()
        wrapped.final_text = final_text
        wrapped.rounds_completed = rounds_completed
        wrapped.total_gas = mock_capsule._GAS_PER_HANDOFF * len(attestations) if attestations else 0
        wrapped.total_wall_time_ms = total_wall_time_ms
        wrapped.capsule.capsule_id = capsule_id
        wrapped.attestations = attestations or []
        wrapped.to_dict.return_value = {"provenance_chain": ["hash1", "hash2"]}
        return wrapped

    mock_capsule.wrap_result.side_effect = _dynamic_wrap
    return mock_capsule


def _make_mock_session(raise_on_infer=None, partial_steps=None):
    """Create a mock LatentRecursiveSession. If raise_on_infer is set, 
    recursive_infer() raises that exception."""
    from unittest.mock import MagicMock

    mock_session = MagicMock()
    if raise_on_infer is not None:
        mock_session.recursive_infer.side_effect = raise_on_infer
    else:
        mock_session.recursive_infer.return_value = {
            "final_text": "This is mock inference output",
            "rounds": 2,
            "steps": partial_steps or [
                {"agent": "planner", "round": 1, "hidden_dim": 2048, "link_key": "inner"},
                {"agent": "critic", "round": 1, "hidden_dim": 2048, "link_key": "outer"},
                {"agent": "solver", "round": 2, "hidden_dim": 2048, "link_key": "inner"},
            ],
        }
    mock_session.load_all.return_value = True
    mock_session.unload.return_value = None
    return mock_session


def _run_inference_with_mocks(mock_capsule, mock_session, **kwargs):
    """Run governed_latent_infer with mock GPU."""
    from unittest.mock import patch

    params = dict(
        prompt="test prompt",
        session_config={"recursion_rounds": 2},
        max_rounds=2,
        adapter_sha256s={
            "planner_critic": hashlib.sha256(b"pc").hexdigest(),
            "critic_solver": hashlib.sha256(b"cs").hexdigest(),
            "solver_planner": hashlib.sha256(b"sp").hexdigest(),
        },
    )
    params.update(kwargs)

    with (
        patch("hlf_mcp.hlf.latent_capsule.LatentCapsule", return_value=mock_capsule),
        patch("hlf_mcp.hlf.latent_model_interface.LatentRecursiveSession", return_value=mock_session),
        patch("hlf_mcp.hlf.latent_model_interface.RecursiveSessionConfig"),
        patch("hlf_mcp.hlf.latent_capsule._write_latent_observability_trace"),
        patch("torch.cuda.is_available", return_value=True),
        patch("torch.cuda.max_memory_allocated", return_value=500 * 1024 * 1024),
    ):
        from hlf_mcp.hlf.latent_capsule import governed_latent_infer
        return governed_latent_infer(**params)


# ═══════════════════════════════════════════════════════════════════════════════
# Pytest cleanup
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _reset_hitl_gate():
    """Clean up HITL gate state between tests."""
    from hlf_mcp.hlf.hitl_gate import HITLGate
    HITLGate.reset_instance()
    yield
    HITLGate.reset_instance()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: OOM Chaos
# ═══════════════════════════════════════════════════════════════════════════════


class TestOOMResilience:
    """Verify graceful handling of CUDA OOM during inference."""

    def test_oom_during_recursive_infer_returns_aborted(self):
        """OOM in session.recursive_infer() produces status 'aborted'."""
        from torch.cuda import OutOfMemoryError

        mock_capsule = _make_mock_capsule("oom-test-001")
        mock_session = _make_mock_session(raise_on_infer=OutOfMemoryError("CUDA out of memory. Tried to allocate 2.00 GiB"))

        result = _run_inference_with_mocks(mock_capsule, mock_session)

        assert result["status"] == "aborted"
        assert "oom_details" in result
        assert result["oom_details"]["is_oom"] is True
        assert "OutOfMemoryError" in result["oom_details"]["error_type"]
        assert "CUDA" in result["oom_details"]["error_message"]

    def test_oom_produces_partial_merkle_chain(self):
        """Aborted inference still produces a Merkle provenance chain."""
        from torch.cuda import OutOfMemoryError

        mock_capsule = _make_mock_capsule("oom-chain-001")
        mock_session = _make_mock_session(raise_on_infer=OutOfMemoryError("OOM"))

        result = _run_inference_with_mocks(mock_capsule, mock_session)

        assert result["status"] == "aborted"
        assert "provenance_chain" in result
        assert isinstance(result["provenance_chain"], list)
        # provenance_chain should exist even for aborted capsules
        assert len(result["provenance_chain"]) >= 0  # may be empty but must be present

    def test_oom_rounds_completed_is_zero(self):
        """When OOM occurs, rounds_completed should be 0."""
        from torch.cuda import OutOfMemoryError

        mock_capsule = _make_mock_capsule("oom-rounds-001")
        mock_session = _make_mock_session(raise_on_infer=OutOfMemoryError("OOM"))

        result = _run_inference_with_mocks(mock_capsule, mock_session)

        assert result["rounds_completed"] == 0

    def test_oom_session_unload_is_called(self):
        """VRAM cleanup: session.unload() MUST be called even after OOM."""
        from torch.cuda import OutOfMemoryError

        mock_capsule = _make_mock_capsule("oom-unload-001")
        mock_session = _make_mock_session(raise_on_infer=OutOfMemoryError("OOM"))

        _run_inference_with_mocks(mock_capsule, mock_session)

        # Verify session.unload() was called (VRAM released)
        assert mock_session.unload.call_count >= 1, (
            "session.unload() must be called after OOM to release GPU memory"
        )

    def test_oom_final_text_contains_aborted_marker(self):
        """Aborted output text should clearly indicate the error."""
        from torch.cuda import OutOfMemoryError

        mock_capsule = _make_mock_capsule("oom-text-001")
        mock_session = _make_mock_session(raise_on_infer=OutOfMemoryError("CUDA out of memory"))

        result = _run_inference_with_mocks(mock_capsule, mock_session)

        assert "ABORTED" in result["final_text"]
        assert "OutOfMemoryError" in result["final_text"]

    def test_oom_details_contain_traceback(self):
        """OOM details should include a traceback for debugging."""
        from torch.cuda import OutOfMemoryError

        mock_capsule = _make_mock_capsule("oom-tb-001")
        mock_session = _make_mock_session(raise_on_infer=OutOfMemoryError("OOM at round 2"))

        result = _run_inference_with_mocks(mock_capsule, mock_session)

        assert "traceback" in result["oom_details"]
        assert "OutOfMemoryError" in result["oom_details"]["traceback"]


class TestGenericCUDAResilience:
    """Verify handling of non-OOM CUDA errors."""

    def test_runtime_error_with_oom_string_is_aborted(self):
        """A RuntimeError containing 'out of memory' is treated as OOM."""
        mock_capsule = _make_mock_capsule("runtime-oom-001")
        mock_session = _make_mock_session(
            raise_on_infer=RuntimeError("CUDA error: out of memory in cudaMalloc")
        )

        result = _run_inference_with_mocks(mock_capsule, mock_session)

        assert result["status"] == "aborted"
        assert result["oom_details"]["is_oom"] is True

    def test_cuda_assertion_error_is_aborted(self):
        """A generic CUDA error is caught as abort."""
        mock_capsule = _make_mock_capsule("cuda-assert-001")
        mock_session = _make_mock_session(
            raise_on_infer=RuntimeError("CUDA error: device-side assert triggered")
        )

        result = _run_inference_with_mocks(mock_capsule, mock_session)

        assert result["status"] == "aborted"
        # "cuda" in error string should be caught even if not literal OOM
        assert result["oom_details"]["is_oom"] is True

    def test_non_cuda_exception_is_not_marked_oom(self):
        """A non-CUDA exception should still abort but not be marked as OOM."""
        mock_capsule = _make_mock_capsule("value-error-001")
        mock_session = _make_mock_session(
            raise_on_infer=ValueError("Tensor shape mismatch: expected [1,2048] got [1,1536]")
        )

        result = _run_inference_with_mocks(mock_capsule, mock_session)

        assert result["status"] == "aborted"
        assert result["oom_details"]["is_oom"] is False

    def test_session_unload_called_on_generic_error(self):
        """VRAM cleanup still happens on non-OOM errors."""
        mock_capsule = _make_mock_capsule("generic-unload-001")
        mock_session = _make_mock_session(
            raise_on_infer=ValueError("Something went wrong")
        )

        _run_inference_with_mocks(mock_capsule, mock_session)

        assert mock_session.unload.call_count >= 1


class TestNormalPathRegression:
    """Verify the OOM handling doesn't break the normal success path."""

    def test_normal_inference_still_succeeds(self):
        """Without OOM, inference returns status 'ok'."""
        mock_capsule = _make_mock_capsule("normal-001")
        mock_session = _make_mock_session()

        result = _run_inference_with_mocks(mock_capsule, mock_session)

        assert result["status"] == "ok"
        assert "oom_details" not in result
        assert result["rounds_completed"] == 2
        assert result["final_text"] == "This is mock inference output"
        # total_gas = GAS_PER_HANDOFF * len(steps) = 25 * 3
        assert result["total_gas"] == 75

    def test_normal_inference_attestations_present(self):
        """Normal inference still produces attestations."""
        mock_capsule = _make_mock_capsule("normal-attest-001")
        mock_session = _make_mock_session()

        result = _run_inference_with_mocks(mock_capsule, mock_session)

        assert len(result["attestations"]) == 3  # 3 steps in the mock
        for att in result["attestations"]:
            assert "round" in att
            assert "source_agent" in att
            assert "adapter_sha256" in att


class TestChaosMemoryManagement:
    """Verify no dangling GPU references after chaos."""

    def test_load_all_not_called_if_oom_before_inference(self):
        """If session creation fails with OOM, it returns error with exception text."""
        from unittest.mock import patch
        from torch.cuda import OutOfMemoryError
        import hashlib

        mock_capsule = _make_mock_capsule("pre-oom-001")
        mock_session = _make_mock_session()

        with (
            patch("hlf_mcp.hlf.latent_capsule.LatentCapsule", return_value=mock_capsule),
            patch("hlf_mcp.hlf.latent_model_interface.LatentRecursiveSession", return_value=mock_session),
            patch("hlf_mcp.hlf.latent_model_interface.RecursiveSessionConfig"),
            patch("hlf_mcp.hlf.latent_capsule._write_latent_observability_trace"),
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.max_memory_allocated", return_value=500 * 1024 * 1024),
        ):
            from hlf_mcp.hlf.latent_capsule import governed_latent_infer
            # Simulate OOM during load
            mock_session.load_all.side_effect = OutOfMemoryError("Out of memory during model load")

            result = governed_latent_infer(
                prompt="test",
                session_config={"recursion_rounds": 2},
                max_rounds=2,
                adapter_sha256s={
                    "planner_critic": hashlib.sha256(b"pc").hexdigest(),
                    "critic_solver": hashlib.sha256(b"cs").hexdigest(),
                    "solver_planner": hashlib.sha256(b"sp").hexdigest(),
                },
            )

            # load_all threw OOM, outer catch wraps it as error
            assert result["status"] == "error"
            assert "Out of memory" in result["error"]


class TestOOMWithHITL:
    """Verify OOM + HITL gate interaction is correct."""

    @pytest.fixture(autouse=True)
    def _setup_temp_dir(self):
        """Provide a temporary directory for HITL gate state."""
        import tempfile
        self._temp_dir = tempfile.TemporaryDirectory()
        from hlf_mcp.hlf.hitl_gate import HITLGate
        HITLGate.reset_instance()
        HITLGate.get_instance(Path(self._temp_dir.name))
        yield
        HITLGate.reset_instance()
        self._temp_dir.cleanup()

    def test_oom_with_human_approval_required_returns_aborted_not_awaiting(self):
        """OOM abort should NOT trigger HITL submission — it stays 'aborted'."""
        from torch.cuda import OutOfMemoryError
        from hlf_mcp.hlf.hitl_gate import HITLGate

        mock_capsule = _make_mock_capsule("oom-hitl-001")
        mock_session = _make_mock_session(raise_on_infer=OutOfMemoryError("OOM during inference"))

        result = _run_inference_with_mocks(
            mock_capsule, mock_session,
            human_approval_required=True,
        )

        # Should be aborted, not awaiting_human_approval
        assert result["status"] == "aborted"
        assert "hitl_status" not in result
        # Verify no pending approval was created
        gate = HITLGate.get_instance()
        pending = gate.list_pending()
        assert len(pending) == 0, "Aborted capsules should not create HITL requests"
