"""Tests for Agent Identity module (Commit 15 of enterprise hardening gauntlet).

Tests cover Ed25519 keypair generation, signing, verification,
serialization (raw bytes + PEM), tamper detection, and integration
with the Bearer token auth flow.

No external network or secrets needed — all cryptographic operations
are purely local.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from hlf_mcp.hlf.agent_identity import (
    AgentIdentity,
    AgentIdentityAuth,
    AgentProof,
    AgentTier,
    IdentityGenerationError,
    ProofVerificationError,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def identity() -> AgentIdentity:
    return AgentIdentity.generate(tier=AgentTier.HEARTH)


@pytest.fixture
def sovereign_identity() -> AgentIdentity:
    return AgentIdentity.generate(tier=AgentTier.SOVEREIGN)


# ---------------------------------------------------------------------------
# Key generation tests
# ---------------------------------------------------------------------------

class TestKeyGeneration:
    """Verify Ed25519 key generation produces valid keypairs."""

    def test_generate_produces_valid_keypair(self):
        identity = AgentIdentity.generate()
        assert identity.has_private_key
        assert identity.agent_id.startswith("hlf-ag-")
        assert len(identity.agent_id) == 23  # "hlf-ag-" + 16 hex chars

    def test_generate_is_random(self):
        """Sequential generations produce different identities."""
        ids = {AgentIdentity.generate().agent_id for _ in range(10)}
        assert len(ids) == 10, "Expected 10 unique agent IDs"

    def test_generate_respects_tier(self):
        identity = AgentIdentity.generate(tier=AgentTier.SOVEREIGN)
        assert identity.tier == AgentTier.SOVEREIGN

    def test_generate_defaults_to_hearth(self):
        identity = AgentIdentity.generate()
        assert identity.tier == AgentTier.HEARTH

    def test_from_private_bytes_roundtrip(self):
        """Identity generated from raw seed matches original."""
        original = AgentIdentity.generate()
        reloaded = AgentIdentity.from_private_bytes(original.private_bytes())
        assert original.agent_id == reloaded.agent_id
        assert original.public_key_bytes() == reloaded.public_key_bytes()

    def test_from_private_bytes_rejects_short_seed(self):
        with pytest.raises(IdentityGenerationError, match="Expected 32-byte"):
            AgentIdentity.from_private_bytes(b"short")

    def test_from_private_bytes_rejects_long_seed(self):
        with pytest.raises(IdentityGenerationError, match="Expected 32-byte"):
            AgentIdentity.from_private_bytes(b"x" * 33)


# ---------------------------------------------------------------------------
# Sign and verify tests
# ---------------------------------------------------------------------------

class TestSignVerify:
    """Verify signing and signature verification."""

    def test_sign_verify_roundtrip(self, identity):
        """Sign a payload and verify it with the public key."""
        proof = identity.sign(b"hello, agent")
        assert AgentIdentity.verify(identity.public_key_bytes(), proof)

    def test_sign_text_convenience(self, identity):
        """sign_text() produces verifiable proofs."""
        proof = identity.sign_text("hello, agent")
        assert AgentIdentity.verify(identity.public_key_bytes(), proof)

    def test_verify_rejects_tampered_payload(self, identity):
        """Tampered payload fails verification."""
        proof = identity.sign(b"original payload")
        tampered = AgentProof(
            agent_id=proof.agent_id,
            payload=b"tampered payload".hex(),
            signature_hex=proof.signature_hex,
            timestamp=proof.timestamp,
            token=proof.token,
        )
        with pytest.raises(ProofVerificationError, match="Signature verification failed"):
            AgentIdentity.verify(identity.public_key_bytes(), tampered)

    def test_verify_rejects_wrong_public_key(self, identity):
        """Verifying with a different agent's public key fails."""
        other = AgentIdentity.generate()
        proof = identity.sign(b"payload")
        with pytest.raises(ProofVerificationError, match="Agent ID mismatch"):
            AgentIdentity.verify(other.public_key_bytes(), proof)

    def test_verify_rejects_expired_proof(self, identity):
        """max_age rejects proofs older than the limit."""
        proof = identity.sign(b"payload")

        # Pretend the proof is 600 seconds old
        with patch("hlf_mcp.hlf.agent_identity.time") as mock_time:
            mock_time.time.return_value = proof.timestamp + 601
            with pytest.raises(ProofVerificationError, match="Proof expired"):
                AgentIdentity.verify(identity.public_key_bytes(), proof, max_age=300)

    def test_verify_accepts_fresh_proof(self, identity):
        """Proof within max_age window is accepted."""
        proof = identity.sign(b"payload")
        with patch("hlf_mcp.hlf.agent_identity.time") as mock_time:
            mock_time.time.return_value = proof.timestamp + 100
            assert AgentIdentity.verify(identity.public_key_bytes(), proof, max_age=300)

    def test_verify_accepts_without_max_age(self, identity):
        """No max_age means any age is accepted."""
        proof = identity.sign(b"payload")
        assert AgentIdentity.verify(identity.public_key_bytes(), proof, max_age=None)

    def test_verify_rejects_altered_token(self, identity):
        """Tampered HMAC token fails verification."""
        proof = identity.sign(b"payload")
        tampered = AgentProof(
            agent_id=proof.agent_id,
            payload=proof.payload,
            signature_hex=proof.signature_hex,
            timestamp=proof.timestamp,
            token="deadbeef" * 8,
        )
        with pytest.raises(ProofVerificationError, match="HMAC token verification failed"):
            AgentIdentity.verify(identity.public_key_bytes(), tampered)


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------

class TestSerialization:
    """Verify key serialization roundtrips."""

    def test_raw_bytes_roundtrip(self, identity):
        """Raw private bytes → from_private_bytes → same identity."""
        raw = identity.private_bytes()
        assert len(raw) == 32
        reloaded = AgentIdentity.from_private_bytes(raw)
        assert reloaded.agent_id == identity.agent_id

    def test_public_bytes_consistency(self, identity):
        """Public key bytes match between original and reloaded."""
        raw = identity.private_bytes()
        reloaded = AgentIdentity.from_private_bytes(raw)
        assert identity.public_key_bytes() == reloaded.public_key_bytes()

    def test_pem_roundtrip(self, identity):
        """PEM encode → decode → same identity."""
        pem = identity.private_pem()
        assert b"-----BEGIN HLF AGENT PRIVATE KEY-----" in pem
        assert b"-----END HLF AGENT PRIVATE KEY-----" in pem
        reloaded = AgentIdentity.from_pem(pem)
        assert reloaded.agent_id == identity.agent_id
        assert reloaded.public_key_bytes() == identity.public_key_bytes()

    def test_public_pem_format(self, identity):
        """Public key PEM has correct format."""
        pem = identity.public_pem()
        assert b"-----BEGIN HLF AGENT PUBLIC KEY-----" in pem
        assert b"-----END HLF AGENT PUBLIC KEY-----" in pem
        assert b"PRIVATE" not in pem

    def test_pem_load_rejects_malformed(self):
        """Malformed PEM raises IdentityGenerationError."""
        with pytest.raises(IdentityGenerationError, match="Missing HLF AGENT PRIVATE KEY"):
            AgentIdentity.from_pem(b"not valid pem")

    def test_pem_load_rejects_non_utf8(self):
        with pytest.raises(IdentityGenerationError, match="not valid UTF-8"):
            AgentIdentity.from_pem(b"\xff\xfe\x00\x00" * 10)


# ---------------------------------------------------------------------------
# AgentProof serialization
# ---------------------------------------------------------------------------

class TestAgentProofSerialization:
    """Verify AgentProof JSON roundtrip."""

    def test_to_json_from_json_roundtrip(self, identity):
        proof = identity.sign(b"test payload")
        json_str = proof.to_json()
        reloaded = AgentProof.from_json(json_str)
        assert reloaded.agent_id == proof.agent_id
        assert reloaded.payload == proof.payload
        assert reloaded.signature_hex == proof.signature_hex
        assert reloaded.timestamp == proof.timestamp
        assert reloaded.token == proof.token

    def test_to_dict_returns_serializable(self):
        proof = AgentProof(
            agent_id="hlf-ag-deadbeef",
            payload=b"hello".hex(),
            signature_hex="a" * 128,
            timestamp=1234567890,
            token="b" * 64,
        )
        d = proof.to_dict()
        assert all(isinstance(v, str) or isinstance(v, int) for v in d.values())


# ---------------------------------------------------------------------------
# Public-only identity
# ---------------------------------------------------------------------------

class TestPublicOnlyIdentity:
    """Verify public-only identity behavior."""

    def test_from_public_bytes_creates_verify_only_identity(self):
        identity = AgentIdentity.generate()
        public_only = AgentIdentity.from_public_bytes(identity.public_key_bytes())
        assert not public_only.has_private_key
        assert public_only.agent_id == identity.agent_id

    def test_public_only_cannot_sign(self):
        identity = AgentIdentity.generate()
        public_only = AgentIdentity.from_public_bytes(identity.public_key_bytes())
        with pytest.raises(IdentityGenerationError, match="Cannot sign"):
            public_only.sign(b"payload")

    def test_public_only_cannot_export_private_bytes(self):
        identity = AgentIdentity.generate()
        public_only = AgentIdentity.from_public_bytes(identity.public_key_bytes())
        with pytest.raises(IdentityGenerationError, match="no private key"):
            public_only.private_bytes()

    def test_public_only_can_verify_original_signatures(self, identity):
        """Public-only identity can verify signatures from the private key."""
        proof = identity.sign(b"payload")
        public_only = AgentIdentity.from_public_bytes(identity.public_key_bytes())
        assert AgentIdentity.verify(public_only.public_key_bytes(), proof)


# ---------------------------------------------------------------------------
# Identity comparisons
# ---------------------------------------------------------------------------

class TestIdentityComparison:
    """Verify equality and hashing."""

    def test_same_keys_equal(self):
        """Identities with same keypair are equal."""
        a = AgentIdentity.generate()
        b = AgentIdentity.from_private_bytes(a.private_bytes())
        assert a == b
        assert hash(a) == hash(b)

    def test_different_keys_not_equal(self):
        a = AgentIdentity.generate()
        b = AgentIdentity.generate()
        assert a != b
        assert hash(a) != hash(b)

    def test_not_equal_to_none(self):
        assert AgentIdentity.generate() != "not an identity"


# ---------------------------------------------------------------------------
# AgentIdentityAuth integration
# ---------------------------------------------------------------------------

class TestAgentIdentityAuth:
    """Verify authentication integration layer."""

    def test_register_and_verify(self, identity):
        """Registered agent can be verified."""
        auth = AgentIdentityAuth()
        auth.register_agent(identity.agent_id, identity.public_key_bytes())
        assert auth.is_registered(identity.agent_id)

    def test_verify_proof_succeeds_for_registered_agent(self, identity):
        """Proof from registered agent passes verification."""
        auth = AgentIdentityAuth()
        auth.register_agent(identity.agent_id, identity.public_key_bytes())
        proof = identity.sign(b"auth payload")
        result = auth.verify_proof(proof)
        assert result is not None
        assert result.agent_id == identity.agent_id

    def test_verify_proof_fails_for_unregistered_agent(self, identity):
        """Unregistered agent proof returns None."""
        auth = AgentIdentityAuth()
        proof = identity.sign(b"auth payload")
        assert auth.verify_proof(proof) is None

    def test_verify_proof_fails_for_tampered_proof(self, identity):
        """Tampered proof returns None (not exception)."""
        auth = AgentIdentityAuth()
        auth.register_agent(identity.agent_id, identity.public_key_bytes())
        proof = identity.sign(b"auth payload")
        tampered = AgentProof(
            agent_id=proof.agent_id,
            payload=b"evil".hex(),
            signature_hex=proof.signature_hex,
            timestamp=proof.timestamp,
            token=proof.token,
        )
        assert auth.verify_proof(tampered) is None

    def test_unregister_removes_agent(self, identity):
        auth = AgentIdentityAuth()
        auth.register_agent(identity.agent_id, identity.public_key_bytes())
        auth.unregister_agent(identity.agent_id)
        assert not auth.is_registered(identity.agent_id)

    def test_register_rejects_invalid_key_length(self):
        auth = AgentIdentityAuth()
        with pytest.raises(IdentityGenerationError, match="Invalid public key"):
            auth.register_agent("test", b"short")

    def test_auth_header_roundtrip(self, identity):
        """Bearer token generated and verified."""
        auth = AgentIdentityAuth()
        auth.register_agent(identity.agent_id, identity.public_key_bytes())

        header = auth.generate_auth_header(identity, payload="POST /api/capsule")
        assert header.startswith("Bearer hlf-ed25519:")

        result = auth.authenticate_token(header)
        assert result is not None
        assert result.agent_id == identity.agent_id

    def test_authenticate_token_ignores_non_ed25519(self):
        """Non-Ed25519 tokens return None (fallthrough to static Bearer)."""
        auth = AgentIdentityAuth()
        result = auth.authenticate_token("Bearer static-token-12345")
        assert result is None

    def test_authenticate_token_rejects_expired(self, identity):
        auth = AgentIdentityAuth()
        auth.register_agent(identity.agent_id, identity.public_key_bytes())
        header = auth.generate_auth_header(identity)
        with patch("hlf_mcp.hlf.agent_identity.time") as mock_time:
            mock_time.time.return_value = time.time() + 1000
            # max_age defaults to 300
            result = auth.authenticate_token(header, max_age=300)
            assert result is None

    def test_authenticate_token_malformed_base64(self):
        auth = AgentIdentityAuth()
        result = auth.authenticate_token("Bearer hlf-ed25519:!!!not-valid-base64!!!")
        assert result is None

    def test_authenticate_token_valid_json_but_not_proof(self):
        """Valid JSON that isn't an AgentProof returns None."""
        import base64
        import json
        fake = base64.b64encode(json.dumps({"not": "a proof"}).encode()).decode()
        auth = AgentIdentityAuth()
        result = auth.authenticate_token(f"Bearer hlf-ed25519:{fake}")
        assert result is None


# ---------------------------------------------------------------------------
# AgentTier
# ---------------------------------------------------------------------------

class TestAgentTier:
    def test_tier_values(self):
        assert AgentTier.HEARTH.value == "hearth"
        assert AgentTier.FORGE.value == "forge"
        assert AgentTier.SOVEREIGN.value == "sovereign"
