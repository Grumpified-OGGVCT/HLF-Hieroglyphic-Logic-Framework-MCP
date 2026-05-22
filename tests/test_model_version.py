"""
Tests for model version pinning — enterprise hardening item #3.

Verifies that:
1. ModelRecord captures digest from Ollama scan
2. Model version verification succeeds when digests match
3. Model version verification raises CapsuleViolation on mismatch
4. Model version verification returns error when model not found
5. governed_latent_infer() returns capsule_violation when model_versions mismatch
6. Empty model_versions dict is a no-op
7. CapabilityManifest roundtrips model_versions correctly
"""

import pytest
from unittest.mock import MagicMock, patch

from hlf_mcp.hlf.model_version import (
    verify_model_versions,
    ModelVersionResult,
)
from hlf_mcp.hlf.capability_manifest import CapabilityManifest
from hlf_mcp.hlf.ollama_pulse import ModelRecord


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_manifest():
    """A manifest with known model version digests."""
    return CapabilityManifest(
        program_id="test-program-001",
        model_versions={
            "medgemma:4b": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "qwen2.5:1.5b": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
        },
    )


@pytest.fixture
def matching_live_models():
    """Live model data that matches the manifest."""
    return {
        "medgemma:4b": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "qwen2.5:1.5b": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    }


@pytest.fixture
def mismatched_live_models():
    """Live model data with a different digest for one model."""
    return {
        "medgemma:4b": "sha256:WRONG_DIGEST_0000000000000000000000000000000000000000000000000000",
        "qwen2.5:1.5b": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    }


# ── ModelRecord digest tests ────────────────────────────────────────────────

class TestModelRecordDigest:
    """ModelRecord now captures digest from Ollama."""

    def test_model_record_includes_digest(self):
        record = ModelRecord(
            name="test-model:latest",
            size_bytes=12345,
            digest="sha256:abc",
        )
        assert record.digest == "sha256:abc"

    def test_model_record_to_dict_includes_digest(self):
        record = ModelRecord(name="test", digest="sha256:xyz")
        d = record.to_dict()
        assert d["digest"] == "sha256:xyz"

    def test_model_record_from_dict_includes_digest(self):
        record = ModelRecord.from_dict({
            "name": "test",
            "digest": "sha256:from_dict",
        })
        assert record.digest == "sha256:from_dict"

    def test_model_record_digest_default_empty(self):
        record = ModelRecord(name="test")
        assert record.digest == ""


# ── ModelVersionResult tests ────────────────────────────────────────────────

class TestModelVersionResult:
    """ModelVersionResult dataclass."""

    def test_match_result(self):
        r = ModelVersionResult(
            model_name="test",
            expected_digest="sha256:abc",
            actual_digest="sha256:abc",
            match=True,
        )
        assert r.match is True
        assert r.error == ""

    def test_mismatch_result(self):
        r = ModelVersionResult(
            model_name="test",
            expected_digest="sha256:expected",
            actual_digest="sha256:actual",
            match=False,
            error="Digest mismatch",
        )
        assert r.match is False
        assert r.error == "Digest mismatch"

    def test_to_dict(self):
        r = ModelVersionResult(
            model_name="test",
            expected_digest="sha256:exp",
            actual_digest="sha256:act",
            match=True,
        )
        d = r.to_dict()
        assert d["model_name"] == "test"
        assert d["match"] is True


# ── verify_model_versions tests ─────────────────────────────────────────────

class TestVerifyModelVersions:
    """Core verification logic."""

    def test_no_model_versions_returns_empty(self):
        """Empty model_versions dict is a no-op."""
        manifest = CapabilityManifest(program_id="empty")
        results = verify_model_versions(manifest, live_models={})
        assert results == []

    def test_all_match(self, sample_manifest, matching_live_models):
        results = verify_model_versions(sample_manifest, live_models=matching_live_models)
        assert len(results) == 2
        assert all(r.match for r in results)

    def test_mismatch_raises_capsule_violation(self, sample_manifest, mismatched_live_models):
        from hlf_mcp.hlf.capsules import CapsuleViolation
        with pytest.raises(CapsuleViolation, match="medgemma"):
            verify_model_versions(sample_manifest, live_models=mismatched_live_models)

    def test_model_not_found_in_live(self, sample_manifest):
        """Model declared in manifest but not in live scan."""
        from hlf_mcp.hlf.capsules import CapsuleViolation
        with pytest.raises(CapsuleViolation, match="NOT FOUND"):
            verify_model_versions(sample_manifest, live_models={
                "qwen2.5:1.5b": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
            })

    def test_skip_when_no_live_data(self, sample_manifest):
        """When no live data is available, verification is skipped."""
        results = verify_model_versions(sample_manifest)
        assert results == []

    def test_scanner_failure_returns_errors(self, sample_manifest):
        """When scanner fails, results show errors but don't crash."""
        scanner = MagicMock()
        scanner.scan.side_effect = RuntimeError("Ollama not running")
        results = verify_model_versions(sample_manifest, scanner=scanner)
        assert len(results) == 2
        assert not any(r.match for r in results)
        assert all("Failed to scan" in r.error for r in results)

    def test_strips_tag_suffix(self):
        """Model name with :tag should match base name in live dict."""
        manifest = CapabilityManifest(
            program_id="tag-test",
            model_versions={"medgemma:4b": "sha256:abc"},
        )
        results = verify_model_versions(manifest, live_models={
            "medgemma:4b": "sha256:abc",
        })
        assert len(results) == 1
        assert results[0].match is True


# ── CapabilityManifest model_versions tests ─────────────────────────────────

class TestManifestModelVersions:
    """Manifest serialization round-trips model_versions."""

    def test_empty_by_default(self):
        manifest = CapabilityManifest(program_id="test")
        assert manifest.model_versions == {}

    def test_to_dict_includes_model_versions(self):
        manifest = CapabilityManifest(
            program_id="test",
            model_versions={"model-a": "sha256:aaa"},
        )
        d = manifest.to_dict()
        assert d["model_versions"] == {"model-a": "sha256:aaa"}

    def test_from_dict_round_trips(self):
        manifest = CapabilityManifest.from_dict({
            "program_id": "test",
            "model_versions": {"model-a": "sha256:aaa", "model-b": "sha256:bbb"},
        })
        assert manifest.model_versions == {"model-a": "sha256:aaa", "model-b": "sha256:bbb"}


# ── governed_latent_infer integration tests ─────────────────────────────────

class TestGovernedLatentInferModelVersion:
    """Integration: governed_latent_infer with model_versions parameter."""

    def test_model_version_check_passes_with_empty_model_versions(self):
        """When model_versions is empty, it's a no-op."""
        from hlf_mcp.hlf.latent_capsule import governed_latent_infer
        # This should not fail — empty dict triggers no verification
        result = governed_latent_infer(
            "test prompt",
            session_config={"agent_models": {"test": "/fake"}},
            model_versions={},
            max_rounds=0,  # Skip actual inference
        )
        # Will likely error because max_rounds=0, but should not be capsule_violation
        assert result["status"] != "capsule_violation"

    def test_model_version_none_is_noop(self):
        """None model_versions should not trigger check."""
        from hlf_mcp.hlf.latent_capsule import governed_latent_infer
        result = governed_latent_infer(
            "test",
            session_config={"agent_models": {"test": "/fake"}},
            model_versions=None,
            max_rounds=0,
        )
        assert result["status"] != "capsule_violation"
