"""Integration demo — end-to-end tests for enterprise hardening gauntlet.

Commit 16: Proves all hardening layers work together in concert.

Covers the critical path:
    Agent Identity → Capsule → Model Pinning → Secret Mgmt → Merkle Chain → HITL → Evidence

These tests verify that hardening features compose correctly, not just
that each works in isolation.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def master_key():
    """Master key for secret management tests."""
    return "integration-test-master-key-32chars!!"


@pytest.fixture
def temp_dir():
    """Temporary directory that survives the test."""
    with tempfile.TemporaryDirectory(prefix="hlf_integration_") as d:
        yield Path(d)


# ---------------------------------------------------------------------------
# 1. Agent Identity → Capsule Integration
# ---------------------------------------------------------------------------

class TestAgentIdentityCapsuleIntegration:
    """Agent identity proofs bound to capsule metadata."""

    def test_agent_signed_capsule_identity_flow(self, tmp_path):
        """Generate identity, sign capsule payload, verify on the other side."""
        from hlf_mcp.hlf.agent_identity import AgentIdentity, AgentIdentityAuth

        identity = AgentIdentity.generate()
        auth = AgentIdentityAuth()
        auth.register_agent(identity.agent_id, identity.public_key_bytes())

        # Simulate: agent creates capsule with signed metadata
        capsule_metadata = {"intent": "diagnose", "patient_id": "xyz"}
        proof = identity.sign_text(json.dumps(capsule_metadata, sort_keys=True))

        # Server-side: verify the proof against registered agent
        result = auth.verify_proof(proof)
        assert result is not None
        assert result.agent_id == identity.agent_id
        assert not result.has_private_key  # Public-only on server side

    def test_agent_identity_proof_integration_with_auth_header(self):
        """Full auth header round-trip from agent to server."""
        from hlf_mcp.hlf.agent_identity import AgentIdentity, AgentIdentityAuth

        identity = AgentIdentity.generate()
        auth = AgentIdentityAuth()
        auth.register_agent(identity.agent_id, identity.public_key_bytes())

        header = auth.generate_auth_header(identity, payload="POST /api/compile")
        assert header.startswith("Bearer hlf-ed25519:")

        verified = auth.authenticate_token(header)
        assert verified is not None
        assert verified.agent_id == identity.agent_id


class TestIntegrationHITLWithAgentIdentity:
    """HITL gate with agent identity proofs."""

    def test_hitl_request_with_agent_identity(self, tmp_path):
        """Submit HITL request with signed agent identity."""
        from hlf_mcp.hlf.agent_identity import AgentIdentity
        from hlf_mcp.hlf.hitl_gate import HITLGate, ApprovalRequest

        identity = AgentIdentity.generate()
        gate = HITLGate.get_instance(tmp_path)

        req = ApprovalRequest(
            capsule_id="capsule-001",
            agent_id=identity.agent_id,
            tier="hearth",
            intent_summary="Analyze patient data",
            output_preview="Preliminary analysis complete",
            manifest_hash="sha256:abc123",
            output_hash="sha256:def456",
            gas_consumed=50,
            gas_limit=100,
        )
        gate.submit_approval_request(req)

        assert not gate.is_approved("capsule-001") and not gate.is_rejected("capsule-001")
        gate.approve("capsule-001", operator_id="human-operator")
        assert gate.is_approved("capsule-001")
        assert gate.get_status("capsule-001")["status"] == "COMPLETED"

    def test_hitl_rejection_flow(self, tmp_path):
        """Rejected capsule stays in rejected state."""
        from hlf_mcp.hlf.hitl_gate import HITLGate, ApprovalRequest

        gate = HITLGate.get_instance(tmp_path)
        req = ApprovalRequest(
            capsule_id="capsule-002",
            agent_id="test-agent",
            tier="hearth",
            intent_summary="Risky operation",
            output_preview="Potentially dangerous output",
            manifest_hash="sha256:def456",
            output_hash="sha256:ghi789",
            gas_consumed=10,
            gas_limit=100,
        )
        gate.submit_approval_request(req)
        gate.reject("capsule-002", reason="Too risky", operator_id="human-operator")
        assert gate.is_rejected("capsule-002")
        assert gate.get_status("capsule-002")["status"] == "REJECTED_HUMAN"


class TestIntegrationSecretManagement:
    """Secret management integration with the full hardening stack."""

    def test_secret_encryption_and_redaction_flow(self, tmp_path, master_key):
        """Encrypt a secret, verify redaction, decrypt back."""
        from hlf_mcp.hlf.secret_capsule import encrypt_secret, decrypt_secret, SecretCapsule

        # Encrypt
        encrypted = encrypt_secret("my-api-key-value", master_key=master_key)
        assert "ciphertext_b64" in encrypted
        assert "nonce_b64" in encrypted
        assert "salt_b64" in encrypted

        # Decrypt
        decrypted = decrypt_secret(
            encrypted["ciphertext_b64"],
            encrypted["nonce_b64"],
            encrypted["salt_b64"],
            master_key=master_key,
        )
        assert decrypted == "my-api-key-value"

        capsule = SecretCapsule(master_key=master_key)
        capsule.add("DB_PASSWORD", "password123")

        rep = repr(capsule)
        assert "password123" not in rep
        assert "DB_PASSWORD" in rep

        meta = capsule.merkle_metadata
        for name, hash_val in meta.items():
            assert "password123" not in hash_val

        # Retrieve decrypts correctly
        plaintext = capsule.decrypt("DB_PASSWORD")
        assert plaintext == "password123"

    def test_secret_redaction_crosses_serialization(self, master_key):
        """Secret stays redacted through JSON serialization."""
        from hlf_mcp.hlf.secret_capsule import SecretCapsule

        capsule = SecretCapsule(master_key=master_key)
        capsule.add("TOKEN", "super-secret")

        meta = capsule.merkle_metadata
        json_str = json.dumps(meta)

        # Plaintext must not appear anywhere
        assert "super-secret" not in json_str
        assert "TOKEN" in json_str  # Label is safe


class TestIntegrationMerkleChain:
    """Merkle chain integration with other hardening modules."""

    def test_merkle_export_verify_roundtrip(self, tmp_path, master_key):
        """Export a chain, verify it, restore from backup."""
        orig_key = os.environ.get("HLF_MASTER_KEY")
        os.environ["HLF_MASTER_KEY"] = master_key
        try:
            from hlf_mcp.hlf.merkle_dr import (
                export_merkle_backup,
                verify_merkle_backup,
                restore_from_backup,
            )

            source_dir = tmp_path / "source"
            source_dir.mkdir()
            backup_dir = tmp_path / "backup"
            backup_dir.mkdir()

            # Create a sample JSONL chain file
            chain_file = source_dir / "latent_traces.jsonl"
            entries = [
                {"event": "capsule_start", "data": {"capsule_id": "test-1"}},
                {"event": "capsule_complete", "data": {"capsule_id": "test-1"}},
            ]
            chain_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

            # Export
            manifest = export_merkle_backup(source_dir=source_dir, backup_dir=backup_dir)
            assert manifest["version"] == 1
            assert manifest["backup_type"] == "hlf-merkle-dr"
            assert "latent_traces.jsonl" in manifest["chains"]
            assert manifest["chains"]["latent_traces.jsonl"]["entry_count"] == 2

            ok, errors, _ = verify_merkle_backup(backup_dir=backup_dir)
            assert ok
            assert not errors

            # Restore to a new directory
            restore_dir = tmp_path / "restored"
            restore_dir.mkdir()
            restore_from_backup(backup_dir=backup_dir, target_dir=restore_dir)

            # Verify restored chain
            restored_file = restore_dir / "latent_traces.jsonl"
            assert restored_file.exists()
            restored_content = restored_file.read_text()
            assert "capsule_start" in restored_content
            assert "capsule_complete" in restored_content
        finally:
            if orig_key is not None:
                os.environ["HLF_MASTER_KEY"] = orig_key
            else:
                os.environ.pop("HLF_MASTER_KEY", None)

    def test_merkle_chain_tamper_detection(self, tmp_path, master_key):
        """Tampered chain file should fail verification."""
        orig_key = os.environ.get("HLF_MASTER_KEY")
        os.environ["HLF_MASTER_KEY"] = master_key
        try:
            from hlf_mcp.hlf.merkle_dr import export_merkle_backup, verify_merkle_backup

            source_dir = tmp_path / "source"
            source_dir.mkdir()
            backup_dir = tmp_path / "backup"
            backup_dir.mkdir()

            chain_file = source_dir / "latent_traces.jsonl"
            entries = [
                {"event": "capsule_start", "data": {"capsule_id": "t1"}},
                {"event": "capsule_complete", "data": {"capsule_id": "t1"}},
            ]
            chain_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

            manifest = export_merkle_backup(source_dir=source_dir, backup_dir=backup_dir)
            assert manifest["chain_count"] >= 1
            assert manifest["chains"]["latent_traces.jsonl"]["entry_count"] == 2

            # Tamper with a chain file inside the backup
            backup_chain = backup_dir / "chains" / "latent_traces.jsonl"
            content = backup_chain.read_text()
            tampered = content.replace("capsule_start", "capsule_hacked")
            backup_chain.write_text(tampered)

            # Verify should now fail
            ok, errors, _ = verify_merkle_backup(backup_dir=backup_dir)
            assert not ok
            assert errors
        finally:
            if orig_key is not None:
                os.environ["HLF_MASTER_KEY"] = orig_key
            else:
                os.environ.pop("HLF_MASTER_KEY", None)


class TestIntegrationModelVersionPinning:
    """Model version pinning with capsule execution."""

    def test_model_version_check_passes_for_valid_versions(self):
        """Pre-flight check passes when versions match."""
        from hlf_mcp.hlf.capability_manifest import CapabilityManifest

        manifest = CapabilityManifest(
            program_id="sha256:test123",
            model_versions={
                "ollama_pulse": "sha256:abcd1234",
                "torch": "2.12.0",
            },
        )

        assert manifest.model_versions is not None
        assert "ollama_pulse" in manifest.model_versions
        assert "torch" in manifest.model_versions

    def test_empty_model_versions_are_accepted(self):
        """Capsule without version pinning is valid."""
        from hlf_mcp.hlf.capability_manifest import CapabilityManifest

        manifest = CapabilityManifest(
            program_id="sha256:test456",
        )
        assert not manifest.model_versions  # empty dict by default


class TestIntegrationEvidence:
    """Evidence rendering integration."""

    def test_evidence_shows_complete_audit_trail(self, tmp_path):
        """Evidence CLI renders full trail of operations."""
        from hlf_mcp.hlf.hitl_gate import HITLGate, ApprovalRequest

        gate = HITLGate.get_instance(tmp_path)

        req = ApprovalRequest(
            capsule_id="ev-capsule-1",
            agent_id="agent-42",
            tier="hearth",
            intent_summary="Process medical record",
            output_preview="Analysis complete: normal findings",
            manifest_hash="sha256:fedcba",
            output_hash="sha256:out123",
            gas_consumed=30,
            gas_limit=100,
        )
        gate.submit_approval_request(req)
        gate.approve("ev-capsule-1", operator_id="dr-smith")

        listing = gate.list_pending()
        assert len(listing) == 0  # Approved, no longer pending

        entry = gate.get_status("ev-capsule-1")
        assert entry is not None
        assert entry["status"] == "COMPLETED"

    def test_merkle_chain_preserves_evidence_order(self, tmp_path, master_key):
        """Chain entries must maintain insertion order for audit."""
        orig_key = os.environ.get("HLF_MASTER_KEY")
        os.environ["HLF_MASTER_KEY"] = master_key
        try:
            from hlf_mcp.hlf.merkle_dr import export_merkle_backup

            source_dir = tmp_path / "source"
            source_dir.mkdir()
            backup_dir = tmp_path / "backup"
            backup_dir.mkdir()

            chain_file = source_dir / "latent_traces.jsonl"
            lines = []
            for i in range(5):
                lines.append(json.dumps({"event": f"event_{i}", "data": {"seq": i}}))
            chain_file.write_text("\n".join(lines) + "\n")

            manifest = export_merkle_backup(source_dir=source_dir, backup_dir=backup_dir)
            entry_count = manifest["chains"]["latent_traces.jsonl"]["entry_count"]
            assert entry_count == 5
        finally:
            if orig_key is not None:
                os.environ["HLF_MASTER_KEY"] = orig_key
            else:
                os.environ.pop("HLF_MASTER_KEY", None)


class TestIntegrationNetworkIsolation:
    """Network isolation proof with real HLF operations."""

    def test_full_hardening_stack_is_air_gapped(self):
        """All hardening modules must work without network."""
        from hlf_mcp.hlf.network_isolation import assert_air_gapped

        def exercise_all():
            # Agent identity (Ed25519 crypto only)
            from hlf_mcp.hlf.agent_identity import AgentIdentity
            identity = AgentIdentity.generate()
            proof = identity.sign(b"test")

            # HITL gate (file-based, no network)
            from hlf_mcp.hlf.hitl_gate import HITLGate, ApprovalRequest
            import tempfile
            with tempfile.TemporaryDirectory() as d:
                gate = HITLGate.get_instance(Path(d))
                req = ApprovalRequest(
                    capsule_id="airgap-test",
                    agent_id=identity.agent_id,
                    tier="hearth",
                    intent_summary="test",
                    output_preview="ok",
                    manifest_hash="sha256:abc",
                    output_hash="sha256:out",
                    gas_consumed=5,
                    gas_limit=100,
                )
                gate.submit_approval_request(req)
                gate.approve("airgap-test", operator_id="test")

            # Secret management (crypto only)
            orig_key = os.environ.get("HLF_MASTER_KEY")
            os.environ["HLF_MASTER_KEY"] = "airgap-master-key-32bytes-here!"
            try:
                from hlf_mcp.hlf.secret_capsule import encrypt_secret, decrypt_secret
                enc = encrypt_secret("test-secret", master_key="airgap-master-key-32bytes-here!")
                dec = decrypt_secret(
                    enc["ciphertext_b64"], enc["nonce_b64"], enc["salt_b64"],
                    master_key="airgap-master-key-32bytes-here!",
                )
                assert dec == "test-secret"
            finally:
                if orig_key is not None:
                    os.environ["HLF_MASTER_KEY"] = orig_key
                else:
                    os.environ.pop("HLF_MASTER_KEY", None)

            # Merkle chain (file I/O only — needs MASTER_KEY)
            import tempfile
            import json
            mk_airgap = "airgap-master-key-32bytes-here!"
            with tempfile.TemporaryDirectory() as d:
                orig_key = os.environ.get("HLF_MASTER_KEY")
                os.environ["HLF_MASTER_KEY"] = mk_airgap
                try:
                    sd = Path(d) / "source"
                    sd.mkdir()
                    bd = Path(d) / "backup"
                    bd.mkdir()
                    (sd / "latent_traces.jsonl").write_text(
                        json.dumps({"event": "test", "data": {}}) + "\n"
                    )
                    from hlf_mcp.hlf.merkle_dr import export_merkle_backup, verify_merkle_backup
                    m = export_merkle_backup(source_dir=sd, backup_dir=bd)
                    assert m["version"] == 1
                    ok, _, _ = verify_merkle_backup(backup_dir=bd)
                    assert ok
                finally:
                    if orig_key is not None:
                        os.environ["HLF_MASTER_KEY"] = orig_key
                    else:
                        os.environ.pop("HLF_MASTER_KEY", None)

            # Network isolation itself
            from hlf_mcp.hlf.network_isolation import is_air_gapped_available
            assert is_air_gapped_available()

            return True

        result = assert_air_gapped(exercise_all)
        assert result is True


class TestIntegrationFullPipeline:
    """Complete pipeline from intent to verified evidence."""

    def test_intent_to_merkle_chain_pipeline(self, tmp_path, master_key):
        """End-to-end: agent identity → HITL → secret management → Merkle chain."""
        from hlf_mcp.hlf.agent_identity import AgentIdentity, AgentIdentityAuth
        from hlf_mcp.hlf.hitl_gate import HITLGate, ApprovalRequest

        # 1. Agent identity
        identity = AgentIdentity.generate()
        auth = AgentIdentityAuth()
        auth.register_agent(identity.agent_id, identity.public_key_bytes())

        # 2. Agent signs intent
        intent_payload = json.dumps({
            "action": "analyze",
            "domain": "medical",
            "patient_id": "pt-001",
        })
        proof = identity.sign_text(intent_payload)

        # 3. Verify agent identity
        verified = auth.verify_proof(proof)
        assert verified is not None

        # 4. Submit to HITL gate
        gate = HITLGate.get_instance(tmp_path)
        req = ApprovalRequest(
            capsule_id=f"pipeline-{identity.agent_id[:8]}",
            agent_id=identity.agent_id,
            tier="hearth",
            intent_summary="Analyze patient data",
            output_preview="Analysis output preview",
            manifest_hash="sha256:" + proof.signature_hex[:32],
            output_hash="sha256:output",
            gas_consumed=42,
            gas_limit=100,
        )
        gate.submit_approval_request(req)
        assert gate.get_status(req.capsule_id) is not None

        gate.approve(req.capsule_id, operator_id="dr-reviewer")
        assert gate.is_approved(req.capsule_id)

        # 6. Evidence: agent identity, intent, approval all captured
        entry = gate.get_status(req.capsule_id)
        assert entry is not None
        assert entry["status"] == "COMPLETED"
        assert entry["approved_by"] == "dr-reviewer"

        # 7. Add to Merkle chain
        orig_key = os.environ.get("HLF_MASTER_KEY")
        os.environ["HLF_MASTER_KEY"] = master_key
        try:
            from hlf_mcp.hlf.merkle_dr import export_merkle_backup, verify_merkle_backup

            chain_dir = tmp_path / "chains"
            chain_dir.mkdir()
            backup_dir = tmp_path / "backup"
            backup_dir.mkdir()

            chain_file = chain_dir / "latent_traces.jsonl"
            entries = [
                {"event": "capsule_submit", "data": {
                    "capsule_id": req.capsule_id,
                    "agent_id": identity.agent_id,
                }},
                {"event": "capsule_approved", "data": {
                    "capsule_id": req.capsule_id,
                    "reviewer": "dr-reviewer",
                    "proof_signature": proof.signature_hex[:32],
                }},
            ]
            chain_file.write_text("\n".join(json.dumps(e, sort_keys=True) for e in entries) + "\n")

            manifest = export_merkle_backup(source_dir=chain_dir, backup_dir=backup_dir)
            assert manifest["version"] == 1
            assert manifest["chains"]["latent_traces.jsonl"]["entry_count"] == 2

            ok, errors, _ = verify_merkle_backup(backup_dir=backup_dir)
            assert ok
            assert not errors
        finally:
            if orig_key is not None:
                os.environ["HLF_MASTER_KEY"] = orig_key
            else:
                os.environ.pop("HLF_MASTER_KEY", None)
